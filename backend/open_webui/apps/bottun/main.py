import os
import time
import uuid
import base64
import json
import re
import pandas as pd
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
import uvicorn
import io
from .services import ConfigService, DatabaseService, AIService, ChartService

app = FastAPI()

# CORS configuration
origins = ["*"] # Allow all for dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Services
config_service = ConfigService()
db_service = DatabaseService(config_service.get_db_config())
# Ensure exception table exists
db_service.init_exception_table()

# Use a more likely model name or allow env override
model_name = os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
ai_service = AIService(model=model_name)

# Init ChartService
base_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(base_dir, "static", "charts")
chart_service = ChartService(static_dir)

# Mount static files
app.mount("/static", StaticFiles(directory=os.path.join(base_dir, "static")), name="static")

# --- Pydantic Models ---
class AnalysisContext(BaseModel):
    kpi: Optional[str] = None
    time_range: Optional[str] = None
    scope: Optional[List[str]] = None
    scope_prompted: Optional[bool] = None

class ChatRequest(BaseModel):
    query: str
    context: Optional[AnalysisContext] = None

class SQLGenerationRequest(BaseModel):
    kpi: str
    time_range: str
    scope: List[str]

class DimensionRequest(BaseModel):
    kpi: str
    dimension_type: str # 'time' or 'organization', 'product', etc.
    current_selection: Optional[List[str]] = [] # For cascading filters e.g. ["product:CT"]

# --- Helper Functions ---

def get_kpi_definition(kpi_name: str, kpi_config: Dict):
    """Finds KPI definition by key or fuzzy match on description."""
    kpi_definitions = kpi_config.get('kpi_definitions', {})
    
    # 1. Exact match
    if kpi_name in kpi_definitions:
        return kpi_name, kpi_definitions[kpi_name]
    
    # 2. Fuzzy match
    print(f"KPI '{kpi_name}' not found exactly. Trying fuzzy match...")
    for k, v in kpi_definitions.items():
        desc = v.get('description', '').lower()
        if kpi_name.lower() in k.lower() or kpi_name.lower() in desc:
            print(f"Fuzzy matched '{kpi_name}' to '{k}'")
            return k, v
            
    return None, None


def _bottun_meta_comment(meta: Dict[str, Any]) -> str:
    payload = json.dumps(meta, ensure_ascii=False, separators=(",", ":"))
    b64 = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return f"<!-- BOTTUN_META: {b64} -->"

# --- Endpoints ---

@app.get("/config/init")
def get_ui_config():
    """Returns the UI configurations for dropdowns and buttons."""
    return config_service.get_ui_mappings()


@app.get("/config/db/health")
def db_healthcheck():
    return db_service.healthcheck()

@app.post("/config/dimension")
def get_dimension_values(request: DimensionRequest):
    """Fetches unique values for a specific dimension of a KPI."""
    print(f"Dimension Request: {request}")
    kpi_config = config_service.get_kpi_config()
    
    kpi_key, kpi_def = get_kpi_definition(request.kpi, kpi_config)
    
    if not kpi_def:
        print(f"KPI '{request.kpi}' not found")
        raise HTTPException(status_code=404, detail="KPI not found")
    
    table_name = kpi_def.get('table_name')
    column_name = None

    if request.dimension_type == 'time':
        column_name = kpi_def.get('time_column')
    else:
        scope_cols = kpi_def.get('scope_columns', {})
        column_name = scope_cols.get(request.dimension_type)
        
    if not table_name or not column_name:
        return {"values": []}
        
    # Pass filters to get_unique_values
    filters = {}
    if request.current_selection:
        scope_cols = kpi_def.get('scope_columns', {})
        for s in request.current_selection:
            if ":" in s:
                cat, val = s.split(":", 1)
                
                # Prevent self-filtering: Don't filter a dimension by itself
                # This allows users to see other options in the dropdown even if one is selected
                if cat == request.dimension_type:
                    continue
                    
                # Map category to actual column name
                filter_col = scope_cols.get(cat)
                if filter_col:
                     filters.setdefault(filter_col, []).append(val)

    values = db_service.get_unique_values(table_name, column_name, filters)
    return {"values": values}

@app.post("/chat/analyze")
def analyze_query(request: ChatRequest):
    """Analyzes user query to find intent and missing parameters."""
    kpi_config = config_service.get_kpi_config()
    ui_mappings = config_service.get_ui_mappings()
    
    # Convert context to dict if exists
    context_dict = request.context.dict() if request.context else {}
    
    analysis = ai_service.analyze_intent(request.query, kpi_config, ui_mappings, context_dict, db_service)
    return analysis

@app.post("/chat/sql")
def generate_and_execute_sql(request: SQLGenerationRequest):
    """Generates SQL based on confirmed params and executes it."""
    kpi_config = config_service.get_kpi_config()
    
    # 1. Generate SQL
    sql = ai_service.generate_sql(request.kpi, request.time_range, request.scope, kpi_config)
    
    # 2. Execute SQL
    # Note: In a real scenario, validate SQL or use read-only user
    result = db_service.execute_query(sql)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    # 3. Generate natural language summary
    summary = ai_service.summarize_result(
        request.kpi, 
        request.time_range, 
        request.scope, 
        result.get('data', []), 
        kpi_config
    )
    
    return {
        "sql": sql,
        "result": result,
        "summary": summary
    }


@app.post("/chat/chart")
def generate_chart(request: SQLGenerationRequest):
    kpi_config = config_service.get_kpi_config()

    sql = ai_service.generate_sql(request.kpi, request.time_range, request.scope, kpi_config)
    result = db_service.execute_query(sql)
    if result.get("error"):
        raise HTTPException(status_code=500, detail=result.get("error"))

    kpi_key, kpi_def = get_kpi_definition(request.kpi, kpi_config)
    title = (kpi_def or {}).get("description") or request.kpi

    rows = result.get("data", []) or []
    months: List[str] = []
    values: List[float] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        m = r.get("month")
        v = r.get("value")
        if m is None or v is None:
            continue
        months.append(str(m))
        try:
            values.append(float(v))
        except Exception:
            continue

    return {
        "title": title,
        "months": months,
        "values": values,
    }

@app.post("/chat/download")
def download_detail(request: SQLGenerationRequest):
    """Generates a detailed SQL (SELECT *) and returns an Excel file."""
    kpi_config = config_service.get_kpi_config()
    
    # Use helper for robust KPI lookup
    kpi_key, kpi_def = get_kpi_definition(request.kpi, kpi_config)
    
    if not kpi_def:
        raise HTTPException(status_code=404, detail=f"KPI '{request.kpi}' not found")
        
    sql_template = kpi_def.get('sql_template')
    if not sql_template:
        raise HTTPException(status_code=400, detail="SQL template not found for KPI")
        
    # 1. Generate WHERE clause (using the matched kpi_key)
    conditions = ai_service.generate_where_clause(kpi_key, request.time_range, request.scope, kpi_config)
    
    # 2. Transform sql_template from SELECT COUNT... to SELECT *
    # Find the position of 'FROM'
    from_index = sql_template.upper().find('FROM')
    if from_index == -1:
        raise HTTPException(status_code=500, detail="Invalid SQL template format")
        
    base_sql = "SELECT * " + sql_template[from_index:]
    sql = base_sql.replace("{conditions}", conditions)
    print(f"Download Detail SQL: {sql}")
    
    # 3. Get Data as DataFrame
    df = db_service.get_df_from_query(sql)
    
    if df.empty:
        raise HTTPException(status_code=404, detail="No data found for the given criteria")
        
    # 4. Generate Excel in memory
    output = io.BytesIO()
    try:
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Details')
    except Exception as e:
        print(f"Excel Generation Error: {e}")
        # Fallback to CSV if Excel fails
        df.to_csv(output, index=False)
        filename = f"{kpi_key}_details.csv"
        return Response(
            content=output.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    
    xlsx_data = output.getvalue()
    
    # 5. Return Response
    filename = f"{kpi_key}_details.xlsx"
    return Response(
        content=xlsx_data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

@app.get("/chat/download/get")
def download_detail_get(
    kpi: str = Query(...),
    time_range: Optional[str] = Query(None),
    scope: List[str] = Query([])
):
    request = SQLGenerationRequest(kpi=kpi, time_range=time_range or "", scope=scope)
    return download_detail(request)

@app.get("/")
def read_root():
    return {"message": "MySQL Chatbot Backend is running"}

# --- OpenAI Compatible Endpoint ---

class OpenAIChatMessage(BaseModel):
    role: str
    content: str

class OpenAIChatCompletionRequest(BaseModel):
    model: str
    messages: List[OpenAIChatMessage]
    stream: Optional[bool] = False


def _extract_bottun_meta(content: str) -> Optional[Dict[str, Any]]:
    try:
        m = re.search(r"<!--\s*BOTTUN_META:\s*([A-Za-z0-9_\-]+=*)\s*-->", content or "")
        if not m:
            return None
        b64 = m.group(1)
        padded = b64 + "=" * ((4 - (len(b64) % 4)) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
        return json.loads(payload)
    except Exception:
        return None

@app.post("/v1/chat/completions")
async def chat_completions(request: OpenAIChatCompletionRequest):
    # 1. Extract latest query
    if not request.messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    
    # 2. Replay history to build context
    current_context = {}
    kpi_config = config_service.get_kpi_config()
    ui_mappings = config_service.get_ui_mappings()
    
    analysis = {}
    
    # Iterate through messages to build up context state
    for msg in request.messages:
        if msg.role == "assistant":
            meta = _extract_bottun_meta(msg.content)
            if meta:
                if "kpi" in meta:
                    current_context["kpi"] = meta.get("kpi")
                if "time_range" in meta:
                    current_context["time_range"] = meta.get("time_range")
                if "scope" in meta:
                    current_context["scope"] = meta.get("scope") if isinstance(meta.get("scope"), list) else []
                if meta.get("scope_prompted") is not None:
                    current_context["scope_prompted"] = bool(meta.get("scope_prompted"))
                if meta.get("unsupported_kpi_notified") is not None:
                    current_context["unsupported_kpi_notified"] = bool(meta.get("unsupported_kpi_notified"))

        if msg.role == "user":
            analysis = ai_service.analyze_intent(msg.content, kpi_config, ui_mappings, current_context, db_service)
            current_context = {
                "kpi": analysis.get("kpi"),
                "time_range": analysis.get("time_range"),
                "scope": analysis.get("scope"),
                "scope_prompted": current_context.get("scope_prompted"),
            }
            
    final_analysis = analysis
    response_text = ""
    meta: Dict[str, Any] = {
        "kpi": final_analysis.get("kpi"),
        "time_range": final_analysis.get("time_range"),
        "scope": final_analysis.get("scope"),
        "missing_params": final_analysis.get("missing_params"),
        "missing_scope_categories": final_analysis.get("missing_scope_categories"),
        "scope_prompted": bool(current_context.get("scope_prompted")),
        "unsupported_kpi": bool(final_analysis.get("unsupported_kpi")),
        "unsupported_kpi_notified": bool(final_analysis.get("unsupported_kpi_notified") or current_context.get("unsupported_kpi_notified")),
        "auto_new_conversation": bool(final_analysis.get("auto_new_conversation")),
    }

    scope_label_map = {
        item.get("value"): item.get("label")
        for item in (ui_mappings.get("scope_options", {}).get("categories", []) or [])
        if isinstance(item, dict)
    }

    def _format_recognized_scope(scope_list: Any) -> str:
        if not isinstance(scope_list, list) or not scope_list:
            return ""

        scope_map: Dict[str, List[str]] = {}
        for s in scope_list:
            if not isinstance(s, str) or ":" not in s:
                continue
            cat, val = s.split(":", 1)
            cat = (cat or "").strip().lower()
            val = (val or "").strip()
            if not cat or not val:
                continue
            scope_map.setdefault(cat, [])
            if val not in scope_map[cat]:
                scope_map[cat].append(val)

        parts = []
        for cat in ["product", "organization", "tools"]:
            vals = scope_map.get(cat) or []
            if not vals:
                continue
            label = scope_label_map.get(cat, cat)
            parts.append(f"{label}={'/'.join(vals)}")
        return "；".join(parts)
    
    if final_analysis.get('response_message'):
        response_text = final_analysis['response_message']
    elif final_analysis.get('missing_params'):
        # Generate question
        missing = final_analysis['missing_params']
        
        # Special handling for su_hour_per_tool to guide user with a full prompt example
        if 'kpi' in missing:
            response_text = "请问您想查询什么指标？（例如：FE人数、机台数量等）"
        elif 'time_range' in missing:
            response_text = f"请提供时间范围（例如：2024年，或者2024-2025）。"
        elif 'scope' in missing:
             # Check for proactive scope
            if final_analysis.get('is_proactive_scope'):
                cats = final_analysis.get('missing_scope_categories', [])
                cat_str = "、".join([scope_label_map.get(c, c) for c in cats])
                kpi = final_analysis.get('kpi')
                recognized = _format_recognized_scope(final_analysis.get('scope'))
                if recognized:
                    response_text = f"已识别到对象范围：{recognized}。请问还需要补充其他对象范围吗？（可补充：{cat_str}；回答“没有/不需要/就这样/全部”即可开始查询）"
                else:
                    response_text = f"请问您需要查询哪些{cat_str}？（或者回答“全部”）"
            else:
                recognized = _format_recognized_scope(final_analysis.get('scope'))
                if recognized:
                    response_text = f"已识别到对象范围：{recognized}。请问还需要补充其他对象范围吗？（回答“没有/不需要/就这样/全部”即可开始查询）"
                else:
                    response_text = "请问这就足够了吗？还需要限制其他部门或产品吗？（回答“没有”开始查询）"

            meta["scope_prompted"] = True
    else:
        # Ready to execute
        try:
            # 1. Generate SQL
            sql = ai_service.generate_sql(
                final_analysis['kpi'], 
                final_analysis['time_range'], 
                final_analysis['scope'], 
                kpi_config
            )
            meta["sql"] = sql
            
            # 2. Execute
            result = db_service.execute_query(sql)
            if result.get("error"):
                raise Exception(result.get("error"))
            
            # 3. Summary
            response_text = ai_service.summarize_result(
                final_analysis['kpi'], 
                final_analysis['time_range'], 
                final_analysis['scope'], 
                result.get('data', []), 
                kpi_config
            )

            pass
        except Exception as e:
            response_text = f"查询过程中发生错误: {str(e)}"

    response_text = (response_text or "").rstrip() + "\n\n" + _bottun_meta_comment(meta)

    # Append Context Footer (Styled HTML for Markdown)
    footer_parts = []
    if final_analysis.get('kpi'):
        footer_parts.append(f"KPI: {final_analysis['kpi']}")
    if final_analysis.get('time_range'):
        footer_parts.append(f"Time: {final_analysis['time_range']}")
    if final_analysis.get('scope'):
        footer_parts.append(f"Scope: {', '.join(final_analysis['scope'])}")
    
    if footer_parts:
        # We handle footer in frontend now to place it below buttons
        pass

    # Return OpenAI format
    return {
        "id": f"chatcmpl-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": request.model,
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": response_text
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0
        }
    }

@app.get("/v1/models")
def list_models():
    bot_config = config_service.get_bot_config()
    bot_id = bot_config.get("bot_id", "bottun-rule-bot")
    bot_name = bot_config.get("bot_name", "KPI Bot")
    profile_image = bot_config.get("profile_image_url", "")
    
    model_data = {
        "id": bot_id,
        "object": "model",
        "created": int(time.time()),
        "owned_by": "bottun",
        "name": bot_name,
        "info": {
            "meta": {
                "is_bottun_rule_bot": True,
                "capabilities": {
                    "feedback": False
                }
            }
        }
    }
    
    if profile_image:
        model_data["info"]["meta"]["profile_image_url"] = profile_image
        
    return {
        "object": "list",
        "data": [model_data]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
