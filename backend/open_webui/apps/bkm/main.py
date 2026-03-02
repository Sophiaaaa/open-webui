import base64
import json
import os
import re
import time
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .services import BkmDataService


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

data_service = BkmDataService()


def _load_yaml_file(path: str) -> Dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _get_bot_config() -> Dict[str, Any]:
    base_dir_local = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(base_dir_local, "config", "bot_config.yaml")
    cfg = _load_yaml_file(config_path)
    return cfg if isinstance(cfg, dict) else {}


def _as_float(v: Any, default: float) -> float:
    try:
        if v is None:
            return default
        return float(v)
    except Exception:
        return default


def _get_action_suggestion_min_score() -> float:
    bot_config = _get_bot_config()
    min_score = _as_float(bot_config.get("action_suggestion_min_score"), 0.75)
    if min_score < 0:
        min_score = 0.0
    if min_score > 1:
        min_score = 1.0
    return float(min_score)

base_dir = os.path.dirname(os.path.abspath(__file__))
assets_dir = os.path.join(base_dir, "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="bkm_assets")


class SearchRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


class AskRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5


class OpenAIChatMessage(BaseModel):
    role: str
    content: str


class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[OpenAIChatMessage]
    stream: Optional[bool] = False


def _bkm_meta_comment(meta: Dict[str, Any]) -> str:
    payload = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"<!-- BKM_META: {b64} -->"


def _extract_bkm_meta(content: str) -> Optional[Dict[str, Any]]:
    try:
        m = re.search(r"<!--\s*BKM_META:\s*([A-Za-z0-9_\-]+=*)\s*-->", content or "")
        if not m:
            return None
        b64 = m.group(1)
        padded = b64 + "=" * ((4 - (len(b64) % 4)) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        return json.loads(payload)
    except Exception:
        return None


@app.get("/config/status")
def get_status(request: Request):
    status = data_service.status()
    status["embedding_cache_key"] = getattr(request.app.state, "EMBEDDING_CACHE_KEY", None)
    status["reranking_cache_key"] = getattr(request.app.state, "RERANKING_CACHE_KEY", None)
    status["rerank_enabled"] = getattr(request.app.state, "RERANKING_FUNCTION", None) is not None
    return status


@app.post("/chat/search")
async def search(request: Request, req: SearchRequest):
    top_k = int(req.top_k or 5)
    top_k = max(1, min(20, top_k))
    embedding_fn = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    rerank_fn = getattr(request.app.state, "RERANKING_FUNCTION", None)
    embedding_key = getattr(request.app.state, "EMBEDDING_CACHE_KEY", "")
    result = await data_service.answer_structured(
        query=req.query,
        top_k=top_k,
        embedding_function=embedding_fn,
        reranking_function=rerank_fn,
        embedding_cache_key=str(embedding_key or ""),
    )
    result["action_suggestion_min_score"] = _get_action_suggestion_min_score()
    return result


@app.post("/chat/ask")
async def ask(request: Request, req: AskRequest):
    top_k = int(req.top_k or 5)
    top_k = max(1, min(20, top_k))
    embedding_fn = getattr(request.app.state, "EMBEDDING_FUNCTION", None)
    rerank_fn = getattr(request.app.state, "RERANKING_FUNCTION", None)
    embedding_key = getattr(request.app.state, "EMBEDDING_CACHE_KEY", "")
    result = await data_service.answer_structured(
        query=req.query,
        top_k=top_k,
        embedding_function=embedding_fn,
        reranking_function=rerank_fn,
        embedding_cache_key=str(embedding_key or ""),
    )
    result["assets_base_url"] = "/bkm/assets"
    result["action_suggestion_min_score"] = _get_action_suggestion_min_score()
    return result


@app.post("/v1/chat/completions")
async def chat_completions(request: OpenAIChatCompletionRequest, raw_request: Request):
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    latest_user_msg = None
    for msg in reversed(request.messages):
        if msg.role == "user":
            latest_user_msg = msg
            break
    if not latest_user_msg:
        raise HTTPException(status_code=400, detail="No user message provided")

    current_context: Dict[str, Any] = {}
    for msg in reversed(request.messages):
        if msg.role != "assistant":
            continue
        meta = _extract_bkm_meta(msg.content)
        if not meta:
            continue
        current_context = meta
        break

    top_k = int(current_context.get("top_k") or 5)
    top_k = max(1, min(20, top_k))

    embedding_fn = getattr(raw_request.app.state, "EMBEDDING_FUNCTION", None)
    rerank_fn = getattr(raw_request.app.state, "RERANKING_FUNCTION", None)
    embedding_key = getattr(raw_request.app.state, "EMBEDDING_CACHE_KEY", "")
    answer = await data_service.answer_structured(
        query=latest_user_msg.content,
        top_k=top_k,
        embedding_function=embedding_fn,
        reranking_function=rerank_fn,
        embedding_cache_key=str(embedding_key or ""),
    )

    meta = {
        "top_k": top_k,
        "causes": answer.get("causes"),
        "actions": answer.get("actions"),
        "docs_by_item": answer.get("docs_by_item"),
        "assets_base_url": "/bkm/assets",
        "action_suggestion_min_score": _get_action_suggestion_min_score(),
    }
    content = f"{answer.get('answer_markdown') or ''}\n\n{_bkm_meta_comment(meta)}"

    return {
        "id": "bkm-chatcmpl",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


@app.get("/v1/models")
def list_models():
    bot_config = _get_bot_config()
    bot_id = bot_config.get("bot_id", "bkm-bot")
    bot_name = bot_config.get("bot_name", "BKM Bot")
    profile_image = bot_config.get("profile_image_url", "")

    model_data: Dict[str, Any] = {
        "id": bot_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "bkm",
        "name": bot_name,
        "info": {
            "meta": {
                "is_bkm_bot": True,
                "capabilities": {"feedback": True},
                "suggestion_prompts": [
                    {
                        "title": ["工艺温度不稳", ""],
                        "content": "工艺温度不稳",
                        "auto_submit": True,
                    }
                ],
            }
        },
    }

    if profile_image:
        model_data["info"]["meta"]["profile_image_url"] = profile_image

    return {"object": "list", "data": [model_data]}
