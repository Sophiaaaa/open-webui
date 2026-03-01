#!/bin/bash

set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT_DIR/backend"

PYTHON_CMD="$(command -v python3 || command -v python)"

PORT="${PORT:-8081}"
HOST="${HOST:-0.0.0.0}"

CONFIG_PATH_DEFAULT="$ROOT_DIR/backend/open_webui/apps/bots/config/bots_config.yaml"
OPEN_WEBUI_BOTS_CONFIG_PATH="${OPEN_WEBUI_BOTS_CONFIG_PATH:-$CONFIG_PATH_DEFAULT}"
export OPEN_WEBUI_BOTS_CONFIG_PATH

BOT_FLAGS_JSON=$($PYTHON_CMD - <<'PY'
import json
import os
from pathlib import Path

def as_bool(v, default):
    if v is None:
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"1","true","t","yes","y","on","enable","enabled"}:
        return True
    if s in {"0","false","f","no","n","off","disable","disabled"}:
        return False
    return default

path = Path(os.environ.get("OPEN_WEBUI_BOTS_CONFIG_PATH") or "").expanduser()
data = {}
try:
    import yaml
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f)
        data = loaded if isinstance(loaded, dict) else {}
except Exception:
    data = {}

bots = data.get("bots") if isinstance(data.get("bots"), dict) else {}
kpi = bots.get("kpi_bot") if isinstance(bots.get("kpi_bot"), dict) else {}
bkm = bots.get("bkm_bot") if isinstance(bots.get("bkm_bot"), dict) else {}

enable_kpi = as_bool(os.getenv("OPEN_WEBUI_ENABLE_KPI_BOT"), as_bool(kpi.get("enabled"), True))
enable_bkm = as_bool(os.getenv("OPEN_WEBUI_ENABLE_BKM_BOT"), as_bool(bkm.get("enabled"), True))

print(json.dumps({"enable_kpi_bot": enable_kpi, "enable_bkm_bot": enable_bkm}, ensure_ascii=False))
PY
)

export BOT_FLAGS_JSON

ENABLE_KPI_BOT=$($PYTHON_CMD - <<'PY'
import json
import os

data = json.loads(os.environ["BOT_FLAGS_JSON"])
print("true" if data.get("enable_kpi_bot") else "false")
PY
)

ENABLE_BKM_BOT=$($PYTHON_CMD - <<'PY'
import json
import os

data = json.loads(os.environ["BOT_FLAGS_JSON"])
print("true" if data.get("enable_bkm_bot") else "false")
PY
)

export OPEN_WEBUI_ENABLE_KPI_BOT="$ENABLE_KPI_BOT"
export OPEN_WEBUI_ENABLE_BKM_BOT="$ENABLE_BKM_BOT"

base_urls="${OPENAI_API_BASE_URLS:-}"
api_keys="${OPENAI_API_KEYS:-${OPENAI_API_KEY:-}}"

urls=()
keys=()

if [[ -n "$base_urls" ]]; then
  IFS=';' read -r -a urls <<<"$base_urls"
  IFS=';' read -r -a keys <<<"$api_keys"
else
  if [[ -n "$api_keys" && "$api_keys" != "sk-placeholder" ]]; then
    urls+=("https://api.openai.com/v1")
    keys+=("$api_keys")
  fi
fi

if [[ "$ENABLE_KPI_BOT" == "true" ]]; then
  urls+=("http://localhost:${PORT}/bottun/v1")
  keys+=("any")
fi

if [[ "$ENABLE_BKM_BOT" == "true" ]]; then
  urls+=("http://localhost:${PORT}/bkm/v1")
  keys+=("any")
fi

export OPENAI_API_BASE_URLS="$(IFS=';'; echo "${urls[*]}")"
export OPENAI_API_KEYS="$(IFS=';'; echo "${keys[*]}")"

export RESET_CONFIG_ON_START="${RESET_CONFIG_ON_START:-True}"
export ENABLE_BASE_MODELS_CACHE="${ENABLE_BASE_MODELS_CACHE:-False}"
export ENABLE_PERSISTENT_CONFIG="${ENABLE_PERSISTENT_CONFIG:-False}"
export SKIP_BASE_MODELS_WARMUP="${SKIP_BASE_MODELS_WARMUP:-True}"

UVICORN_BIN="${OPEN_WEBUI_UVICORN_BIN:-}"
if [[ -z "$UVICORN_BIN" ]]; then
  if [[ -x "/Users/sophia/anaconda3/envs/open-webui/bin/uvicorn" ]]; then
    UVICORN_BIN="/Users/sophia/anaconda3/envs/open-webui/bin/uvicorn"
  else
    UVICORN_BIN="$(command -v uvicorn || true)"
  fi
fi

if [[ -n "$UVICORN_BIN" ]]; then
  exec "$UVICORN_BIN" open_webui.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips '*'
fi

exec "$PYTHON_CMD" -m uvicorn open_webui.main:app --host "$HOST" --port "$PORT" --forwarded-allow-ips '*'
