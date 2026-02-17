import json
import os
import re
import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

from langchain_core.documents import Document


def _coerce_str_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    s = str(value).strip()
    return [s] if s else []


def _tokenize(text: str) -> List[str]:
    if not text:
        return []
    tokens: List[str] = []
    tokens.extend([t.lower() for t in re.findall(r"[A-Za-z0-9_]+", text)])
    tokens.extend([c for c in re.findall(r"[\u4e00-\u9fff]", text)])
    return tokens


def _tf(tokens: Iterable[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for t in tokens:
        out[t] = out.get(t, 0) + 1
    return out


def _cosine(a: Dict[str, int], a_norm: float, b: Dict[str, int], b_norm: float) -> float:
    if a_norm <= 0 or b_norm <= 0:
        return 0.0
    if len(a) > len(b):
        a, b = b, a
        a_norm, b_norm = b_norm, a_norm

    dot = 0.0
    for k, v in a.items():
        bv = b.get(k)
        if bv:
            dot += float(v * bv)
    return dot / (a_norm * b_norm)


def _norm(tf_map: Dict[str, int]) -> float:
    return sum(float(v * v) for v in tf_map.values()) ** 0.5


def _cosine_vec(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    n = min(len(a), len(b))
    dot = 0.0
    a2 = 0.0
    b2 = 0.0
    for i in range(n):
        av = float(a[i])
        bv = float(b[i])
        dot += av * bv
        a2 += av * av
        b2 += bv * bv
    if a2 <= 0 or b2 <= 0:
        return 0.0
    return dot / (math.sqrt(a2) * math.sqrt(b2))


@dataclass
class BkmSource:
    pdf: str
    pages: List[int]


@dataclass
class BkmPair:
    action: str
    root_cause: str
    source: Optional[BkmSource] = None
    evidence: Optional[str] = None
    raw: Optional[dict] = None


@dataclass
class BkmItem:
    id: str
    title: str
    question: str
    pairs: List[BkmPair]
    raw: dict


class BkmDataService:
    def __init__(self, json_path: Optional[str] = None):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        default_path = os.path.join(base_dir, "data", "bkm.json")
        self.json_path = (json_path or os.getenv("BKM_JSON_PATH") or default_path).strip()
        self._items: List[BkmItem] = []
        self._index: List[Tuple[Dict[str, int], float]] = []
        self._loaded_mtime: Optional[float] = None

        self._docs: List[Dict[str, Any]] = []
        self._doc_embeddings: List[List[float]] = []
        self._embedding_cache_key: Optional[str] = None

    def status(self) -> Dict[str, Any]:
        self._ensure_loaded()
        return {
            "json_path": self.json_path,
            "items": len(self._items),
            "loaded": self._loaded_mtime is not None,
            "mtime": self._loaded_mtime,
            "docs": len(self._docs),
        }

    def _ensure_loaded(self) -> None:
        try:
            mtime = os.path.getmtime(self.json_path)
        except Exception:
            mtime = None

        if mtime is not None and self._loaded_mtime is not None and mtime == self._loaded_mtime:
            return

        self._items = self._load_items()
        self._docs = self._build_docs(self._items)
        self._doc_embeddings = []
        self._embedding_cache_key = None
        self._index = []
        for it in self._items:
            text = "\n".join(
                [
                    it.title or "",
                    it.question or "",
                    "\n".join([p.action for p in it.pairs]),
                    "\n".join([p.root_cause for p in it.pairs]),
                    "\n".join([p.evidence or "" for p in it.pairs]),
                ]
            )
            tf_map = _tf(_tokenize(text))
            self._index.append((tf_map, _norm(tf_map)))
        self._loaded_mtime = mtime

    def _build_docs(self, items: List[BkmItem]) -> List[Dict[str, Any]]:
        docs: List[Dict[str, Any]] = []
        for it in items:
            for idx, p in enumerate(it.pairs):
                pdf = (p.source.pdf if p.source else "")
                pages = (p.source.pages if p.source else [])
                docs.append(
                    {
                        "doc_id": f"{it.id}:{idx}",
                        "item_id": it.id,
                        "title": it.title,
                        "question": it.question,
                        "action": p.action,
                        "root_cause": p.root_cause,
                        "evidence": p.evidence,
                        "pdf": str(pdf or "").strip(),
                        "pages": [int(x) for x in (pages or []) if isinstance(x, int) and x > 0],
                    }
                )
        return docs

    def _doc_text(self, doc: Dict[str, Any]) -> str:
        parts = [
            str(doc.get("title") or ""),
            str(doc.get("question") or ""),
            f"Action: {str(doc.get('action') or '').strip()}",
            f"Root Cause: {str(doc.get('root_cause') or '').strip()}",
            str(doc.get("evidence") or ""),
        ]
        return "\n".join([p for p in parts if (p or "").strip()]).strip()

    async def _ensure_doc_embeddings(
        self,
        embedding_function,
        embedding_cache_key: str,
    ) -> None:
        self._ensure_loaded()
        if not self._docs:
            self._doc_embeddings = []
            self._embedding_cache_key = embedding_cache_key
            return
        if self._doc_embeddings and self._embedding_cache_key == embedding_cache_key:
            return
        texts = [self._doc_text(d) for d in self._docs]
        embeddings = await embedding_function(texts, prefix=None, user=None)
        out: List[List[float]] = []
        if isinstance(embeddings, list):
            for e in embeddings:
                if isinstance(e, list):
                    out.append([float(x) for x in e])
        self._doc_embeddings = out
        self._embedding_cache_key = embedding_cache_key

    async def answer_structured(
        self,
        query: str,
        top_k: int,
        embedding_function,
        reranking_function,
        embedding_cache_key: str,
    ) -> Dict[str, Any]:
        q = (query or "").strip()
        if not q:
            return {
                "query": query,
                "causes": [],
                "actions": [],
                "docs_by_item": {},
                "answer_markdown": "请输入问题。",
            }

        if embedding_function is None:
            return self._answer_structured_lexical(query=q, top_k=int(top_k or 5))

        await self._ensure_doc_embeddings(embedding_function, embedding_cache_key)
        if not self._docs or not self._doc_embeddings:
            return {
                "query": query,
                "causes": [],
                "actions": [],
                "docs_by_item": {},
                "answer_markdown": "BKM 数据未加载，请检查 JSON 路径或文件内容。",
            }

        q_emb = await embedding_function(q, prefix=None, user=None)
        q_vec = [float(x) for x in (q_emb or [])] if isinstance(q_emb, list) else []
        if not q_vec:
            return self._answer_structured_lexical(query=q, top_k=int(top_k or 5))

        scored: List[Tuple[float, int]] = []
        for i, emb in enumerate(self._doc_embeddings):
            score = _cosine_vec(q_vec, emb)
            scored.append((score, i))
        scored.sort(key=lambda x: x[0], reverse=True)

        cand_n = max(int(top_k or 5) * 6, 20)
        cand = scored[: min(len(scored), cand_n)]
        if not cand:
            return {
                "query": query,
                "causes": [],
                "actions": [],
                "docs_by_item": {},
                "answer_markdown": "未检索到匹配条目，请换个问法或提供更多关键词。",
            }

        cand_docs: List[Dict[str, Any]] = [self._docs[i] for _, i in cand]
        cand_texts = [self._doc_text(d) for d in cand_docs]
        documents = [Document(page_content=t, metadata={"doc_id": d.get("doc_id")}) for d, t in zip(cand_docs, cand_texts)]

        final_scores: List[float]
        if reranking_function is not None:
            import asyncio

            raw_scores = await asyncio.to_thread(reranking_function, q, documents, None)
            final_scores = [float(x) for x in (raw_scores or [])]
        else:
            final_scores = [float(s) for s, _ in cand]

        ranked: List[Tuple[float, Dict[str, Any]]] = []
        for s, d in zip(final_scores, cand_docs):
            ranked.append((float(s), d))
        ranked.sort(key=lambda x: x[0], reverse=True)

        top_docs = ranked[: max(1, min(50, int(top_k or 5) * 6))]
        score_vals = [s for s, _ in top_docs]
        s_min = min(score_vals) if score_vals else 0.0
        s_max = max(score_vals) if score_vals else 1.0
        denom = (s_max - s_min) if (s_max - s_min) > 1e-9 else 1.0

        def norm_score(s: float) -> float:
            return max(0.0, min(1.0, (s - s_min) / denom))

        docs_by_item: Dict[str, List[Dict[str, Any]]] = {}
        causes_map: Dict[str, Dict[str, Any]] = {}
        actions_map: Dict[str, Dict[str, Any]] = {}

        for s, d in top_docs:
            ns = norm_score(s)
            pdf = str(d.get("pdf") or "").strip()
            pages = d.get("pages") or []
            snippet = str(d.get("evidence") or d.get("question") or "").strip()
            action = str(d.get("action") or "").strip()
            rc = str(d.get("root_cause") or "").strip()

            related_ids: List[str] = []
            if rc:
                cid = f"cause:{rc}"
                related_ids.append(cid)
                entry = causes_map.get(cid) or {"id": cid, "text": rc, "score": 0.0}
                entry["score"] = max(float(entry.get("score") or 0.0), ns)
                causes_map[cid] = entry
            if action:
                aid = f"action:{action}"
                related_ids.append(aid)
                entry = actions_map.get(aid) or {"id": aid, "text": action, "score": 0.0}
                entry["score"] = max(float(entry.get("score") or 0.0), ns)
                actions_map[aid] = entry

            doc_rows: List[Dict[str, Any]] = []
            if pdf and pages:
                for p in pages:
                    doc_rows.append(
                        {
                            "pdf": pdf,
                            "page": int(p),
                            "title": f"{pdf}(页 {int(p)})",
                            "score": ns,
                            "snippet": snippet,
                        }
                    )
            elif pdf:
                doc_rows.append(
                    {
                        "pdf": pdf,
                        "page": None,
                        "title": pdf,
                        "score": ns,
                        "snippet": snippet,
                    }
                )

            for rid in related_ids:
                if rid not in docs_by_item:
                    docs_by_item[rid] = []
                docs_by_item[rid].extend(doc_rows)

        causes = sorted(list(causes_map.values()), key=lambda x: float(x.get("score") or 0.0), reverse=True)
        actions = sorted(list(actions_map.values()), key=lambda x: float(x.get("score") or 0.0), reverse=True)

        for k, v in list(docs_by_item.items()):
            v.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
            dedup: Dict[Tuple[str, Any], Dict[str, Any]] = {}
            for row in v:
                key = (str(row.get("pdf") or ""), row.get("page"))
                if key not in dedup:
                    dedup[key] = row
            docs_by_item[k] = list(dedup.values())[:10]

        lines: List[str] = []
        lines.append(f"关于“{q}”的问题，搜索回答如下，请参考。")
        lines.append("")
        lines.append("原因：")
        for c in causes[:5]:
            lines.append(f"- {c['text']}")
        lines.append("")
        lines.append("行动建议：")
        for a in actions[:5]:
            lines.append(f"- {a['text']}")

        return {
            "query": query,
            "causes": causes[:8],
            "actions": actions[:8],
            "docs_by_item": docs_by_item,
            "answer_markdown": "\n".join(lines).strip(),
        }

    def _answer_structured_lexical(self, query: str, top_k: int) -> Dict[str, Any]:
        items = self.search(query=query, top_k=top_k)
        if not items:
            return {
                "query": query,
                "causes": [],
                "actions": [],
                "docs_by_item": {},
                "answer_markdown": "未检索到匹配条目，请换个问法或提供更多关键词。",
            }

        score_vals = [float(it.get("score") or 0.0) for it in items]
        s_min = min(score_vals) if score_vals else 0.0
        s_max = max(score_vals) if score_vals else 1.0
        denom = (s_max - s_min) if (s_max - s_min) > 1e-9 else 1.0

        def norm_score(s: float) -> float:
            return max(0.0, min(1.0, (float(s) - s_min) / denom))

        docs_by_item: Dict[str, List[Dict[str, Any]]] = {}
        causes_map: Dict[str, Dict[str, Any]] = {}
        actions_map: Dict[str, Dict[str, Any]] = {}

        for it in items:
            ns = norm_score(float(it.get("score") or 0.0))
            for p in it.get("pairs", []) or []:
                action = str(p.get("action") or "").strip()
                rc = str(p.get("root_cause") or "").strip()
                snippet = str(p.get("evidence") or it.get("question") or "").strip()
                src = p.get("source") or {}
                pdf = str(src.get("pdf") or "").strip()
                pages = src.get("pages") or []

                related_ids: List[str] = []
                if rc:
                    cid = f"cause:{rc}"
                    related_ids.append(cid)
                    entry = causes_map.get(cid) or {"id": cid, "text": rc, "score": 0.0}
                    entry["score"] = max(float(entry.get("score") or 0.0), ns)
                    causes_map[cid] = entry
                if action:
                    aid = f"action:{action}"
                    related_ids.append(aid)
                    entry = actions_map.get(aid) or {"id": aid, "text": action, "score": 0.0}
                    entry["score"] = max(float(entry.get("score") or 0.0), ns)
                    actions_map[aid] = entry

                doc_rows: List[Dict[str, Any]] = []
                if pdf and pages:
                    for page in pages:
                        if isinstance(page, int) and page > 0:
                            doc_rows.append(
                                {
                                    "pdf": pdf,
                                    "page": int(page),
                                    "title": f"{pdf}(页 {int(page)})",
                                    "score": ns,
                                    "snippet": snippet,
                                }
                            )
                elif pdf:
                    doc_rows.append(
                        {
                            "pdf": pdf,
                            "page": None,
                            "title": pdf,
                            "score": ns,
                            "snippet": snippet,
                        }
                    )

                for rid in related_ids:
                    if rid not in docs_by_item:
                        docs_by_item[rid] = []
                    docs_by_item[rid].extend(doc_rows)

        causes = sorted(list(causes_map.values()), key=lambda x: float(x.get("score") or 0.0), reverse=True)
        actions = sorted(list(actions_map.values()), key=lambda x: float(x.get("score") or 0.0), reverse=True)

        for k, v in list(docs_by_item.items()):
            v.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
            dedup: Dict[Tuple[str, Any], Dict[str, Any]] = {}
            for row in v:
                key = (str(row.get("pdf") or ""), row.get("page"))
                if key not in dedup:
                    dedup[key] = row
            docs_by_item[k] = list(dedup.values())[:10]

        lines: List[str] = []
        lines.append(f"关于“{query}”的问题，搜索回答如下，请参考。")
        lines.append("")
        lines.append("原因：")
        for c in causes[:5]:
            lines.append(f"- {c['text']}")
        lines.append("")
        lines.append("行动建议：")
        for a in actions[:5]:
            lines.append(f"- {a['text']}")

        return {
            "query": query,
            "causes": causes[:8],
            "actions": actions[:8],
            "docs_by_item": docs_by_item,
            "answer_markdown": "\n".join(lines).strip(),
        }

    def _load_items(self) -> List[BkmItem]:
        if not os.path.isfile(self.json_path):
            return []

        with open(self.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        raw_items: List[dict]
        if isinstance(data, list):
            raw_items = [x for x in data if isinstance(x, dict)]
        elif isinstance(data, dict):
            maybe_list = data.get("items") or data.get("data") or data.get("records")
            if isinstance(maybe_list, list):
                raw_items = [x for x in maybe_list if isinstance(x, dict)]
            else:
                raw_items = [data]
        else:
            return []

        items: List[BkmItem] = []
        for idx, raw in enumerate(raw_items):
            item_id = str(raw.get("id") or raw.get("uuid") or raw.get("key") or idx)
            title = str(raw.get("title") or raw.get("问题") or raw.get("问题标题") or raw.get("problem_title") or "").strip()
            question = str(
                raw.get("question")
                or raw.get("问题描述")
                or raw.get("描述")
                or raw.get("problem")
                or raw.get("problem_description")
                or title
                or ""
            ).strip()

            pairs = self._extract_pairs(raw)
            if not title:
                title = question[:60]
            items.append(BkmItem(id=item_id, title=title, question=question, pairs=pairs, raw=raw))

        return items

    def _extract_pairs(self, raw: dict) -> List[BkmPair]:
        pairs: List[BkmPair] = []

        raw_pairs = raw.get("pairs") or raw.get("qa") or raw.get("action_rootcause")
        if isinstance(raw_pairs, list):
            for p in raw_pairs:
                if not isinstance(p, dict):
                    continue
                action = str(p.get("action") or p.get("Action") or p.get("对应action") or p.get("处理动作") or "").strip()
                rc = str(p.get("root_cause") or p.get("rootCause") or p.get("Root Cause") or p.get("root cause") or p.get("对应root cause") or p.get("根因") or "").strip()
                evidence = (
                    str(p.get("evidence") or p.get("excerpt") or p.get("quote") or p.get("page_content") or "").strip()
                    or None
                )
                source = self._extract_source(p) or self._extract_source(raw)
                if action or rc:
                    pairs.append(BkmPair(action=action, root_cause=rc, evidence=evidence, source=source, raw=p))

            if pairs:
                return pairs

        actions = _coerce_str_list(raw.get("action") or raw.get("Action") or raw.get("对应action") or raw.get("处理动作"))
        root_causes = _coerce_str_list(
            raw.get("root_cause")
            or raw.get("rootCause")
            or raw.get("Root Cause")
            or raw.get("root cause")
            or raw.get("对应root cause")
            or raw.get("根因")
        )

        evidence = (
            str(raw.get("evidence") or raw.get("excerpt") or raw.get("quote") or raw.get("page_content") or "").strip()
            or None
        )
        source = self._extract_source(raw)

        n = max(len(actions), len(root_causes), 1)
        for i in range(n):
            action = actions[i] if i < len(actions) else ""
            rc = root_causes[i] if i < len(root_causes) else ""
            if action or rc:
                pairs.append(BkmPair(action=action, root_cause=rc, evidence=evidence, source=source, raw=raw))

        if not pairs and (evidence or source):
            pairs.append(BkmPair(action="", root_cause="", evidence=evidence, source=source, raw=raw))
        return pairs

    def _extract_source(self, raw: dict) -> Optional[BkmSource]:
        ds = (
            raw.get("data_source")
            or raw.get("dataSource")
            or raw.get("data source")
            or raw.get("source")
            or raw.get("来源")
            or raw.get("数据来源")
        )

        pdf = None
        pages: List[int] = []

        if isinstance(ds, dict):
            pdf = (
                ds.get("pdf")
                or ds.get("pdf_name")
                or ds.get("pdfName")
                or ds.get("pdf name")
                or ds.get("file")
                or ds.get("filename")
                or ds.get("文件")
            )
            pages_val = ds.get("page") or ds.get("pages") or ds.get("page_no") or ds.get("pageNo") or ds.get("页") or ds.get("页码")
            pages = self._coerce_pages(pages_val)
        elif isinstance(ds, list):
            for entry in ds:
                if not isinstance(entry, dict):
                    continue
                if pdf is None:
                    pdf = entry.get("pdf") or entry.get("file") or entry.get("filename")
                pages.extend(self._coerce_pages(entry.get("page") or entry.get("pages") or entry.get("页码")))
        elif isinstance(ds, str):
            pdf = ds

        if pdf is None:
            pdf = raw.get("pdf") or raw.get("pdf_name") or raw.get("pdfName")
        if not pages:
            pages = self._coerce_pages(raw.get("page") or raw.get("pages") or raw.get("页码") or raw.get("页"))

        pdf_str = str(pdf).strip() if pdf is not None else ""
        pages = [p for p in pages if isinstance(p, int) and p > 0]
        if not pdf_str and not pages:
            return None
        return BkmSource(pdf=pdf_str, pages=sorted(set(pages)))

    def _coerce_pages(self, value: Any) -> List[int]:
        if value is None:
            return []
        if isinstance(value, int):
            return [value]
        if isinstance(value, list):
            out: List[int] = []
            for v in value:
                out.extend(self._coerce_pages(v))
            return out
        s = str(value).strip()
        if not s:
            return []
        out: List[int] = []
        for part in re.split(r"[^0-9]+", s):
            part = part.strip()
            if not part:
                continue
            try:
                out.append(int(part))
            except Exception:
                continue
        return out

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        self._ensure_loaded()
        q = (query or "").strip()
        if not q:
            return []

        q_tf = _tf(_tokenize(q))
        q_norm = _norm(q_tf)

        scored: List[Tuple[float, int]] = []
        for i, (tf_map, tf_norm) in enumerate(self._index):
            score = _cosine(q_tf, q_norm, tf_map, tf_norm)
            if score > 0:
                scored.append((score, i))
        scored.sort(key=lambda x: x[0], reverse=True)

        out: List[Dict[str, Any]] = []
        for score, idx in scored[: max(1, min(50, top_k))]:
            it = self._items[idx]
            out.append(self._serialize_item(it, score))
        return out

    def compose_answer(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        items = self.search(query=query, top_k=top_k)

        if not items:
            return {
                "query": query,
                "answer_markdown": "未检索到匹配条目，请换个问法或提供更多关键词。",
                "items": [],
                "references": [],
            }

        refs: Dict[Tuple[str, int], bool] = {}
        for it in items:
            for p in it.get("pairs", []) or []:
                src = p.get("source") or {}
                pdf = str(src.get("pdf") or "").strip()
                for page in src.get("pages") or []:
                    if pdf and isinstance(page, int) and page > 0:
                        refs[(pdf, page)] = True

        references = [
            {"pdf": pdf, "page": page}
            for (pdf, page) in sorted(refs.keys(), key=lambda x: (x[0], x[1]))
        ]

        lines: List[str] = []
        lines.append("已为你从 BKM 手册中检索到以下相关条目（可点击右侧来源跳转验证）：")
        lines.append("")
        for idx, it in enumerate(items, start=1):
            title = it.get("title") or f"条目 {idx}"
            score = it.get("score")
            lines.append(f"### {idx}. {title}")
            q = it.get("question")
            if q:
                lines.append(f"- 问题：{q}")
            pairs = it.get("pairs") or []
            for pidx, p in enumerate(pairs, start=1):
                action = (p.get("action") or "").strip()
                rc = (p.get("root_cause") or "").strip()
                lines.append(f"- 结论 {pidx}：")
                if action:
                    lines.append(f"  - Action：{action}")
                if rc:
                    lines.append(f"  - Root Cause：{rc}")
                ev = (p.get("evidence") or "").strip()
                if ev:
                    lines.append(f"  - 证据：{ev}")
                src = p.get("source") or {}
                pdf = (src.get("pdf") or "").strip()
                pages = src.get("pages") or []
                if pdf and pages:
                    page_str = ", ".join([str(x) for x in pages])
                    lines.append(f"  - 来源：{pdf}（页码：{page_str}）")
            if isinstance(score, (int, float)):
                lines.append("")

        return {
            "query": query,
            "answer_markdown": "\n".join(lines).strip(),
            "items": items,
            "references": references,
        }

    def _serialize_item(self, item: BkmItem, score: float) -> Dict[str, Any]:
        pairs: List[Dict[str, Any]] = []
        for idx, p in enumerate(item.pairs):
            pairs.append(
                {
                    "id": f"{item.id}:{idx}",
                    "action": p.action,
                    "root_cause": p.root_cause,
                    "evidence": p.evidence,
                    "source": (
                        {"pdf": p.source.pdf, "pages": p.source.pages} if p.source else None
                    ),
                }
            )
        return {
            "id": item.id,
            "title": item.title,
            "question": item.question,
            "score": round(float(score), 6),
            "pairs": pairs,
        }
