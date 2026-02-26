from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _coerce_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        out: list[str] = []
        for v in value:
            s = str(v).strip()
            if s:
                out.append(s)
        return out
    s = str(value).strip()
    return [s] if s else []


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    if s in {"1", "true", "t", "yes", "y", "on", "enable", "enabled"}:
        return True
    if s in {"0", "false", "f", "no", "n", "off", "disable", "disabled"}:
        return False
    return default


def _default_config_path() -> Path:
    return (Path(__file__).resolve().parent / "config" / "bots_config.yaml").resolve()


def _read_yaml_file(path: Path) -> dict[str, Any]:
    try:
        import yaml  # type: ignore
    except Exception:
        return {}

    try:
        if not path.exists():
            return {}
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


@dataclass(frozen=True)
class BotAccessConfig:
    group_names: tuple[str, ...]
    user_ids: tuple[str, ...]
    user_emails: tuple[str, ...]


@dataclass(frozen=True)
class BotsRuntimeConfig:
    enable_kpi_bot: bool
    enable_bkm_bot: bool
    kpi_bot_id: str
    bkm_bot_id: str
    kpi_access: BotAccessConfig
    bkm_access: BotAccessConfig
    config_path: str


def load_bots_runtime_config() -> BotsRuntimeConfig:
    env_path = (os.getenv("OPEN_WEBUI_BOTS_CONFIG_PATH") or "").strip()
    path = Path(env_path).expanduser().resolve() if env_path else _default_config_path()
    data = _read_yaml_file(path)

    bots = data.get("bots") if isinstance(data.get("bots"), dict) else {}
    kpi = bots.get("kpi_bot") if isinstance(bots.get("kpi_bot"), dict) else {}
    bkm = bots.get("bkm_bot") if isinstance(bots.get("bkm_bot"), dict) else {}

    kpi_access_raw = kpi.get("access") if isinstance(kpi.get("access"), dict) else {}
    bkm_access_raw = bkm.get("access") if isinstance(bkm.get("access"), dict) else {}

    enable_kpi_bot = _as_bool(os.getenv("OPEN_WEBUI_ENABLE_KPI_BOT"), _as_bool(kpi.get("enabled"), True))
    enable_bkm_bot = _as_bool(os.getenv("OPEN_WEBUI_ENABLE_BKM_BOT"), _as_bool(bkm.get("enabled"), True))

    kpi_bot_id = str(kpi.get("bot_id") or "bottun-rule-bot").strip()
    bkm_bot_id = str(bkm.get("bot_id") or "bkm-bot").strip()

    def _parse_access(raw: dict[str, Any]) -> BotAccessConfig:
        group_names = tuple(_coerce_str_list(raw.get("group_names") or raw.get("groups")))
        user_ids = tuple(_coerce_str_list(raw.get("user_ids") or raw.get("users")))
        user_emails = tuple(_coerce_str_list(raw.get("user_emails") or raw.get("emails")))
        return BotAccessConfig(group_names=group_names, user_ids=user_ids, user_emails=user_emails)

    return BotsRuntimeConfig(
        enable_kpi_bot=enable_kpi_bot,
        enable_bkm_bot=enable_bkm_bot,
        kpi_bot_id=kpi_bot_id,
        bkm_bot_id=bkm_bot_id,
        kpi_access=_parse_access(kpi_access_raw),
        bkm_access=_parse_access(bkm_access_raw),
        config_path=str(path),
    )


def is_user_allowed_for_bot(
    user: Any,
    access: BotAccessConfig,
    user_group_names: Iterable[str],
) -> bool:
    role = str(getattr(user, "role", "") or "").strip().lower()
    if role == "admin":
        return True

    uid = str(getattr(user, "id", "") or "").strip()
    email = str(getattr(user, "email", "") or "").strip().lower()
    if uid and uid in set(access.user_ids):
        return True
    if email and email in {e.lower() for e in access.user_emails}:
        return True

    allowed_groups = {g.strip().lower() for g in access.group_names if str(g).strip()}
    if not allowed_groups:
        return False
    user_groups = {str(g).strip().lower() for g in user_group_names if str(g).strip()}
    return len(allowed_groups.intersection(user_groups)) > 0
