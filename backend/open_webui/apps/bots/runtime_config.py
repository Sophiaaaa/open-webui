from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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
class BotsRuntimeConfig:
    enable_kpi_bot: bool
    enable_bkm_bot: bool
    config_path: str


def load_bots_runtime_config() -> BotsRuntimeConfig:
    env_path = (os.getenv("OPEN_WEBUI_BOTS_CONFIG_PATH") or "").strip()
    path = Path(env_path).expanduser().resolve() if env_path else _default_config_path()
    data = _read_yaml_file(path)

    bots = data.get("bots") if isinstance(data.get("bots"), dict) else {}
    kpi = bots.get("kpi_bot") if isinstance(bots.get("kpi_bot"), dict) else {}
    bkm = bots.get("bkm_bot") if isinstance(bots.get("bkm_bot"), dict) else {}

    enable_kpi_bot = _as_bool(os.getenv("OPEN_WEBUI_ENABLE_KPI_BOT"), _as_bool(kpi.get("enabled"), True))
    enable_bkm_bot = _as_bool(os.getenv("OPEN_WEBUI_ENABLE_BKM_BOT"), _as_bool(bkm.get("enabled"), True))

    return BotsRuntimeConfig(
        enable_kpi_bot=enable_kpi_bot,
        enable_bkm_bot=enable_bkm_bot,
        config_path=str(path),
    )

