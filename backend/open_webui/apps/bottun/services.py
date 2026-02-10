import yaml
import mysql.connector
import requests
import pandas as pd
import json
import os
import re
import uuid
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, Any, List

# --- Config Service ---
class ConfigService:
    def __init__(self, config_dir: str = None):
        if config_dir is None:
            # Get directory of current file
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.config_dir = os.path.join(base_dir, "config")
        else:
            self.config_dir = config_dir

        self.db_config = self._load_yaml("db_config.yaml")
        self.ui_mappings = self._load_yaml("ui_mappings.yaml")
        self.kpi_config = self._load_first_yaml(["config_kpi.yaml", "kpi_config.yaml"])
        self.bot_config = self._load_yaml("bot_config.yaml")

    def _load_yaml(self, filename: str) -> Dict[str, Any]:
        path = os.path.join(self.config_dir, filename)
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f)
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            return {}

    def _load_first_yaml(self, filenames: List[str]) -> Dict[str, Any]:
        for filename in filenames:
            path = os.path.join(self.config_dir, filename)
            if not os.path.exists(path):
                continue
            loaded = self._load_yaml(filename)
            if loaded:
                return loaded
        return {}

    def get_db_config(self):
        cfg = dict(self.db_config or {})

        env_overrides = {
            "host": os.getenv("BOTTUN_DB_HOST"),
            "port": os.getenv("BOTTUN_DB_PORT"),
            "user": os.getenv("BOTTUN_DB_USER"),
            "password": os.getenv("BOTTUN_DB_PASSWORD"),
            "database": os.getenv("BOTTUN_DB_DATABASE"),
        }

        for key, value in env_overrides.items():
            if value is None or value == "":
                continue
            if key == "port":
                try:
                    cfg[key] = int(value)
                except ValueError:
                    continue
            else:
                cfg[key] = value

        return cfg

    def get_ui_mappings(self):
        # Enhance UI mappings with KPI-specific allowed scopes from kpi_config
        import copy
        mappings = copy.deepcopy(self.ui_mappings)
        kpi_defs = self.kpi_config.get('kpi_definitions', {})
        
        # level2_mapping is nested inside kpi_levels
        kpi_levels = mappings.get('kpi_levels', {})
        level2_mapping = kpi_levels.get('level2_mapping', {})
        
        for category, kpis in level2_mapping.items():
            for kpi in kpis:
                kpi_val = kpi.get('value')
                if kpi_val in kpi_defs:
                    kpi['allowed_scopes'] = kpi_defs[kpi_val].get('allowed_scopes', [])
        
        return mappings

    def get_kpi_config(self):
        return self.kpi_config

    def get_bot_config(self):
        return self.bot_config

# --- Database Service ---
class DatabaseService:
    def __init__(self, db_config: Dict[str, Any]):
        self.config = db_config

    def get_connection(self):
        host = self.config.get("host", "localhost")
        port = self.config.get("port", 3306)
        user = self.config.get("user", "root")
        password = self.config.get("password", "")
        database = self.config.get("database", "")

        candidates = [host]
        if host == "localhost":
            candidates = ["::1", "localhost"]

        last_error: Exception | None = None

        for h in candidates:
            try:
                return mysql.connector.connect(
                    host=h,
                    port=port,
                    user=user,
                    password=password,
                    database=database,
                )
            except Exception as e:
                last_error = e

        if last_error is not None:
            print(f"DB Connection Error: {last_error}")
        return None

    def healthcheck(self) -> Dict[str, Any]:
        configured_host = self.config.get("host", "localhost")
        port = self.config.get("port", 3306)
        user = self.config.get("user", "root")
        database = self.config.get("database", "")

        candidates = [configured_host]
        if configured_host == "localhost":
            candidates = ["::1", "localhost"]

        conn = None
        last_error: Exception | None = None

        for h in candidates:
            try:
                conn = mysql.connector.connect(
                    host=h,
                    port=port,
                    user=user,
                    password=self.config.get("password", ""),
                    database=database,
                )
                actual_host = h
                break
            except Exception as e:
                last_error = e

        if conn is None:
            return {
                "ok": False,
                "host": configured_host,
                "port": port,
                "user": user,
                "database": database,
                "error": str(last_error) if last_error else "DB connection failed",
                "attempts": candidates,
            }

        try:
            cursor = conn.cursor()
            cursor.execute("SELECT USER(), CURRENT_USER(), @@version")
            row = cursor.fetchone()
            return {
                "ok": True,
                "host": configured_host,
                "actual_host": actual_host,
                "port": port,
                "user": user,
                "database": database,
                "server_user": row[0] if row else None,
                "current_user": row[1] if row else None,
                "server_version": row[2] if row else None,
            }
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def init_exception_table(self):
        """Creates the exception table if it doesn't exist."""
        sql_create = """
        CREATE TABLE IF NOT EXISTS unsupported_kpi_logs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id VARCHAR(50),
            user_query TEXT,
            time_range VARCHAR(50),
            scope TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        conn = self.get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute(sql_create)
                
                # Check if user_id column exists (for migration)
                cursor.execute("SHOW COLUMNS FROM unsupported_kpi_logs LIKE 'user_id'")
                result = cursor.fetchone()
                if not result:
                    print("Adding missing column 'user_id' to unsupported_kpi_logs...")
                    cursor.execute("ALTER TABLE unsupported_kpi_logs ADD COLUMN user_id VARCHAR(50) AFTER id")
                
                conn.commit()
                print("Exception table initialized/verified.")
            except Exception as e:
                print(f"Error initializing exception table: {e}")
            finally:
                conn.close()

    def log_exception(self, query: str, time_range: str, scope: List[str]):
        """Logs unsupported KPI requests."""
        sql = "INSERT INTO unsupported_kpi_logs (user_query, time_range, scope) VALUES (%s, %s, %s)"
        conn = self.get_connection()
        if conn:
            try:
                cursor = conn.cursor()
                scope_str = json.dumps(scope, ensure_ascii=False) if scope else "[]"
                cursor.execute(sql, (query, time_range, scope_str))
                conn.commit()
                print(f"Logged unsupported KPI request: {query}")
            except Exception as e:
                print(f"Error logging exception: {e}")
            finally:
                conn.close()

    def get_unique_values(self, table_name: str, column_name: str, filters: Dict[str, List[str]] = None) -> List[str]:
        conn = self.get_connection()
        if not conn:
            return []
            
        cursor = conn.cursor()
        try:
            where_clause = f"{column_name} IS NOT NULL"
            
            # Add cascading filters
            if filters:
                for col, vals in filters.items():
                    if not vals: continue
                    if len(vals) == 1:
                        where_clause += f" AND {col} = '{vals[0]}'"
                    else:
                        vals_str = ", ".join([f"'{v}'" for v in vals])
                        where_clause += f" AND {col} IN ({vals_str})"
            
            # Search query logic is handled in frontend/API for simplicity, 
            # but usually we'd add 'LIKE %query%' here if needed.
            
            sql = f"SELECT DISTINCT {column_name} FROM {table_name} WHERE {where_clause} ORDER BY {column_name} ASC LIMIT 100"
            cursor.execute(sql)
            results = cursor.fetchall()
            return [str(row[0]) for row in results]
        except Exception as e:
            print(f"Error fetching unique values: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def find_exact_match(
        self,
        table_name: str,
        column_name: str,
        value: str,
        filters: Dict[str, List[str]] | None = None,
        case_insensitive: bool = True,
    ) -> str | None:
        if not value:
            return None

        if not re.fullmatch(r"[A-Za-z0-9_]+", table_name or ""):
            return None
        if not re.fullmatch(r"[A-Za-z0-9_]+", column_name or ""):
            return None

        conn = self.get_connection()
        if not conn:
            return None

        cursor = conn.cursor()
        try:
            where_parts: List[str] = [f"{column_name} IS NOT NULL"]
            params: List[Any] = []

            if case_insensitive:
                where_parts.append(f"LOWER({column_name}) = LOWER(%s)")
            else:
                where_parts.append(f"{column_name} = %s")
            params.append(value)

            if filters:
                for col, vals in filters.items():
                    if not vals:
                        continue
                    if not re.fullmatch(r"[A-Za-z0-9_]+", col or ""):
                        continue
                    if len(vals) == 1:
                        where_parts.append(f"{col} = %s")
                        params.append(vals[0])
                    else:
                        placeholders = ",".join(["%s"] * len(vals))
                        where_parts.append(f"{col} IN ({placeholders})")
                        params.extend(vals)

            where_clause = " AND ".join(where_parts)
            sql = f"SELECT DISTINCT {column_name} FROM {table_name} WHERE {where_clause} LIMIT 1"
            cursor.execute(sql, tuple(params))
            row = cursor.fetchone()
            return str(row[0]) if row and row[0] is not None else None
        except Exception as e:
            print(f"Error finding exact match: {e}")
            return None
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def execute_query(self, sql: str) -> Dict[str, Any]:
        conn = self.get_connection()
        if not conn:
            return {"error": "DB connection failed", "data": [], "columns": []}
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(sql)
            results = cursor.fetchall()
            return {"data": results, "columns": cursor.column_names}
        except Exception as e:
            return {"error": str(e)}
        finally:
            if conn:
                conn.close()

    def get_df_from_query(self, sql: str) -> pd.DataFrame:
        conn = self.get_connection()
        if not conn:
            return pd.DataFrame()
        try:
            return pd.read_sql(sql, conn)
        except Exception as e:
            print(f"Error reading SQL to DF: {e}")
            return pd.DataFrame()
        finally:
            if conn:
                conn.close()

# --- Chart Service ---
class ChartService:
    def __init__(self, static_dir: str):
        self.static_dir = static_dir
        if not os.path.exists(static_dir):
            os.makedirs(static_dir)

    def generate_chart(self, data: List[Dict[str, Any]], kpi_label: str) -> str:
        if not data:
            return None
        
        df = pd.DataFrame(data)
        if df.empty:
            return None
            
        # Basic logic to determine x and y
        # Prioritize time columns for X
        time_cols = [
            c
            for c in df.columns
            if 'Month' in c or 'Date' in c or 'FY' in c or 'WrMonth' in c or c.lower() in {'month', 'date'}
        ]
        # Identify numeric columns
        value_cols = []
        for c in df.columns:
            # Check if column is numeric
            if pd.api.types.is_numeric_dtype(df[c]):
                value_cols.append(c)
        
        # If no numeric columns found by type, try to infer (e.g. from SQL results that might be strings)
        if not value_cols:
             for c in df.columns:
                 try:
                     df[c] = pd.to_numeric(df[c])
                     value_cols.append(c)
                 except:
                     pass

        if not value_cols:
            return None
            
        y_col = value_cols[0]
        # Avoid using the same column for X and Y if possible
        potential_x = [c for c in df.columns if c != y_col]
        x_col = None
        
        # Pick best X
        for tc in time_cols:
            if tc in potential_x:
                x_col = tc
                break
        
        if not x_col and potential_x:
            x_col = potential_x[0]
            
        if not x_col:
            x_col = df.index.name or 'index'

        plt.figure(figsize=(10, 6))
        sns.set_style("whitegrid")
        
        # Try to set Chinese font support
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'PingFang SC', 'sans-serif'] 
        plt.rcParams['axes.unicode_minus'] = False
        
        try:
            if x_col in time_cols or len(df) > 10:
                # Line chart for time series or many points
                chart = sns.lineplot(data=df, x=x_col, y=y_col, marker='o')
                plt.title(f"{kpi_label} Trend")
            else:
                # Bar chart for categorical
                chart = sns.barplot(data=df, x=x_col, y=y_col)
                plt.title(f"{kpi_label} Distribution")
                
            plt.xticks(rotation=45)
            plt.tight_layout()
            
            filename = f"chart_{uuid.uuid4().hex}.png"
            filepath = os.path.join(self.static_dir, filename)
            plt.savefig(filepath)
            plt.close()
            
            return filename
        except Exception as e:
            print(f"Chart generation failed: {e}")
            plt.close()
            return None

# --- AI Service (OpenAI Compatible / Accelerated) ---
class AIService:
    def __init__(self, model: str = "qwen2.5-coder:1.5b", base_url: str = "http://localhost:11434/v1"):
        self.model = model
        self.base_url = base_url

    def generate_response(self, prompt: str) -> str:
        try:
            print(f"Calling Accelerated AI Service with model {self.model}...")
            response = requests.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "你是一个精确的数据分析助手。请始终使用中文进行回复。只在要求返回 JSON 时返回原始 JSON 数据。"},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()['choices'][0]['message']['content'].strip()
            print("AI Service responded successfully.")
            return result
        except Exception as e:
            print(f"AI Service Error: {e}")
            if isinstance(e, requests.exceptions.ConnectionError):
                print("Connection Error: Is Ollama running at localhost:11434?")
            return ""

    def analyze_intent(self, query: str, kpi_config: Dict, ui_mappings: Dict, context: Dict = None, db_service: Any = None) -> Dict[str, Any]:
        # 0. Initialize from context if provided
        context = context or {}
        context_kpi = context.get('kpi')
        context_time = context.get('time_range')
        context_scope = context.get('scope') or []
        scope_prompted = bool(context.get('scope_prompted'))

        # 1. Pre-check for direct KPI matches (Exact or Keyword based)
        kpi_definitions = kpi_config.get('kpi_definitions', {})
        
        # Priority mapping for common queries (ordered by specificity)
        priority_keywords = [
            # Full label matches (highest priority)
            ("fe人数统计", "fe_count"),
            ("os人数统计", "os_count"),
            ("工程师人数统计", "fe_count"),
            ("外包人数统计", "os_count"),
            ("机台数量统计", "machine_count"),
            ("chamber数量统计", "chamber_count"),

            # Analysis Intent matches
            ("fe人数分析", "fe_count"),
            ("os人数分析", "os_count"),
            ("工程师人数分析", "fe_count"),
            ("外包人数分析", "os_count"),
            ("机台数量分析", "machine_count"),
            ("chamber数量分析", "chamber_count"),
            
            # SU Hour per Tool
            ("su hour per tool", "su_hour_per_tool"),
            ("startup hour per tool", "su_hour_per_tool"),
            ("su hour", "su_hour_per_tool"),
            ("su工时", "su_hour_per_tool"),
            ("平均装机时间", "su_hour_per_tool"),
            ("平均装机小时数", "su_hour_per_tool"),
            ("平均装机小时", "su_hour_per_tool"),
            ("装机时间", "su_hour_per_tool"),
            ("装机工时", "su_hour_per_tool"),
            ("平均每台的装机结果", "su_hour_per_tool"),
            ("平均每台装机结果", "su_hour_per_tool"),
            ("机台装机时间", "su_hour_per_tool"),
            ("每机台装机时间", "su_hour_per_tool"),
            
            # Keywords
            ("fe人数", "fe_count"),
            ("fe数量", "fe_count"),
            ("fe", "fe_count"),
            ("field engineer", "fe_count"),
            ("外协", "os_count"),
            ("os", "os_count"),
            ("机台", "machine_count"),
            ("机器", "machine_count"),
            ("machine", "machine_count"),
            ("chamber", "chamber_count"),
            ("小室", "chamber_count"),
            ("人数统计", "headcount"),
            ("人数", "headcount"),
            ("人员", "headcount")
        ]

        # Check if the query contains a NEW KPI
        query_lower = query.lower()
        new_kpi = None
        for kw, kpi_key in priority_keywords:
            if kw in query_lower:
                new_kpi = kpi_key
                break
        
        # Reset Logic: If a new KPI is detected, we treat it as a fresh question
        # UNLESS the new KPI is the same as the context KPI, then it might be a refinement.
        if new_kpi and new_kpi != context_kpi:
            print(f"New KPI detected: {new_kpi}. Resetting context.")
            matched_kpi = new_kpi
            found_scopes = []
            extracted_time = None # Time might need re-extraction
            
            # Re-extract time from the current query since we reset context
            # (Logic below will handle extraction, but we ensure we don't carry over old time)
        else:
            # Continue with context
            matched_kpi = context_kpi or new_kpi
            found_scopes = context_scope
            extracted_time = context_time

        # 2. Extract Time and Scope manually
        import re
        from datetime import datetime
        known_products = ["CT", "3DI", "SPS", "ES", "SSP", "TPS", "TS", "FSI", "Certas", "SD", "Epion", "FPD"]

        time_all_intent_strong = (
            bool(re.search(r"(所有|全部)\s*范围", query))
            or bool(re.search(r"(所有|全部)\s*(时间|日期|月份|月度|年度|财年|年|月)", query))
            or bool(re.search(r"(所有|全部)(的)?(时间范围|日期范围|月份范围|时间|日期)", query))
            or bool(re.search(r"(不限制|不限|不限定|不设限|无限制)\s*(时间|日期|月份|月度|年度|财年|时间范围|日期范围)?", query))
            or bool(re.search(r"(时间|日期|月份|月度|年度|财年|时间范围|日期范围)\s*(不限制|不限|不限定|不设限|无限制)", query))
            or bool(re.search(r"(不筛选|不做筛选|不需要筛选|不过滤|不过滤)\s*(时间|日期|月份|时间范围|日期范围)?", query))
            or bool(re.search(r"(时间|日期|月份|时间范围|日期范围)\s*(不筛选|不做筛选|不需要筛选|不过滤|不过滤)", query))
            or bool(re.search(r"(all\s*time|any\s*time|no\s*time\s*filter|without\s*time\s*filter|no\s*date\s*filter)", query_lower))
        )

        time_all_intent_weak = (
            query_lower.strip() in {"all", "all time", "any", "any time", "全部", "所有", "不限", "不限制", "不限定"}
            and not extracted_time
            and bool(context_kpi or context_scope)
        )

        time_all_intent = time_all_intent_strong or time_all_intent_weak
        
        # Pre-process shortcuts
        current_date = datetime.now()
        current_year = current_date.year
        current_month = current_date.month

        def _mm(m: int) -> str:
            return f"{m:02d}"

        def _ym(year: int, month: int) -> str:
            return f"{year}{_mm(month)}"

        def _natural_year_range(year: int) -> str:
            return f"{_ym(year, 1)}-{_ym(year, 12)}"

        def _natural_quarter_range(year: int, q: int) -> str:
            q = max(1, min(4, q))
            start_month = (q - 1) * 3 + 1
            end_month = start_month + 2
            return f"{_ym(year, start_month)}-{_ym(year, end_month)}"

        def _fiscal_year_range(fy_end_year: int) -> str:
            start_year = fy_end_year - 1
            return f"{_ym(start_year, 4)}-{_ym(fy_end_year, 3)}"

        def _fiscal_half_range(fy_end_year: int, half: int) -> str:
            start_year = fy_end_year - 1
            if half == 1:
                return f"{_ym(start_year, 4)}-{_ym(start_year, 9)}"
            return f"{_ym(start_year, 10)}-{_ym(fy_end_year, 3)}"

        def _fiscal_quarter_range(fy_end_year: int, q: int) -> str:
            start_year = fy_end_year - 1
            q = max(1, min(4, q))
            if q == 1:
                return f"{_ym(start_year, 4)}-{_ym(start_year, 6)}"
            if q == 2:
                return f"{_ym(start_year, 7)}-{_ym(start_year, 9)}"
            if q == 3:
                return f"{_ym(start_year, 10)}-{_ym(start_year, 12)}"
            return f"{_ym(fy_end_year, 1)}-{_ym(fy_end_year, 3)}"

        def _normalize_time_expressions(text: str) -> str:
            t = text

            # Natural year keywords
            if "今年" in t or "本年" in t:
                t = t.replace("今年", f" {_natural_year_range(current_year)} ").replace("本年", f" {_natural_year_range(current_year)} ")
            if "去年" in t:
                t = t.replace("去年", f" {_natural_year_range(current_year - 1)} ")
            if "明年" in t:
                t = t.replace("明年", f" {_natural_year_range(current_year + 1)} ")

            # Month formats: 2025年3月 / 25年3月份
            def repl_month_cn(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                mo = int(m.group(2))
                return _ym(y, mo)

            t = re.sub(r"(20\d{2}|\d{2})\s*年\s*(\d{1,2})\s*月(?:份)?", repl_month_cn, t)

            # Compact month: 202505 / 2025-05 / 2025/05
            t = re.sub(r"\b(20\d{2})[-/](0?[1-9]|1[0-2])\b", lambda m: _ym(int(m.group(1)), int(m.group(2))), t)

            # Natural quarter: 2025年第三季度 / 25年3季度
            quarter_map = {"一": 1, "二": 2, "三": 3, "四": 4, "1": 1, "2": 2, "3": 3, "4": 4}

            def repl_quarter_cn(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                qraw = m.group(2)
                q = quarter_map.get(qraw, 1)
                return _natural_quarter_range(y, q)

            t = re.sub(r"(20\d{2}|\d{2})\s*年\s*第?([一二三四1234])\s*季度", repl_quarter_cn, t)
            t = re.sub(r"(20\d{2}|\d{2})\s*年\s*([1234])\s*季度", repl_quarter_cn, t)

            # Natural quarter (Q format): 25年Q4 / 2025年Q4
            def repl_quarter_q(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                q = int(m.group(2))
                return _natural_quarter_range(y, q)

            t = re.sub(r"(20\d{2}|\d{2})\s*年\s*[Qq]([1-4])", repl_quarter_q, t)

            # Chinese year formats: 2024年 / 24年
            def repl_year_cn(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                return _natural_year_range(y)

            t = re.sub(r"(20\d{2})\s*年", repl_year_cn, t)
            t = re.sub(r"(\d{2})\s*年", repl_year_cn, t)

            # Year to year: 2024-2025 (years)
            def repl_year_range(m):
                y1 = int(m.group(1))
                y2 = int(m.group(2))
                return f"{_ym(y1, 1)}-{_ym(y2, 12)}"

            t = re.sub(r"(20\d{2})\s*[-~至到]\s*(20\d{2})", repl_year_range, t)

            # Fiscal half-year: FY26 2H / FY26 H2 / FY26 下半期 / FY26 上半期
            def repl_fy_half(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                half_raw = (m.group(2) or "").upper()
                if half_raw in {"1H", "H1", "上半期", "H1"}:
                    return _fiscal_half_range(y, 1)
                if half_raw in {"2H", "H2", "下半期"}:
                    return _fiscal_half_range(y, 2)
                return _fiscal_year_range(y)

            t = re.sub(r"\bFY\s*(\d{2}|20\d{2})\s*(1H|2H|H1|H2|上半期|下半期)\b", repl_fy_half, t, flags=re.IGNORECASE)

            # Fiscal quarter: FY26 Q1/Q2/Q3/Q4
            def repl_fy_q(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                q = int(m.group(2))
                return _fiscal_quarter_range(y, q)

            t = re.sub(r"\bFY\s*(\d{2}|20\d{2})\s*Q([1-4])\b", repl_fy_q, t, flags=re.IGNORECASE)

            # Fiscal year: FY26 / FY2026
            def repl_fy(m):
                y = int(m.group(1))
                if y < 100:
                    y = 2000 + y
                return _fiscal_year_range(y)

            t = re.sub(r"\bFY\s*(\d{2}|20\d{2})\b", repl_fy, t, flags=re.IGNORECASE)

            return t
        
        # Fiscal Year Logic: Starts April 1st
        fy_start_year = current_year if current_month >= 4 else current_year - 1
        fy_end_year = fy_start_year + 1

        if "当前财年" in query:
            query = query.replace("当前财年", f" {fy_start_year}04-{fy_end_year}03 ")

        if "半期" in query:
            if 4 <= current_month <= 9:
                query = query.replace("半期", f" {fy_start_year}04-{fy_start_year}09 ")
            else:
                query = query.replace("半期", f" {fy_start_year}10-{fy_end_year}03 ")

        query = _normalize_time_expressions(query)

        if time_all_intent_strong or (time_all_intent_weak and not extracted_time):
            extracted_time = "all"

        # 2a. Extract Time first to avoid misidentifying it as SN
        new_time = None
        range_match = re.search(r'(20\d{4})-(20\d{4})', query)
        if range_match:
            new_time = f"{range_match.group(1)}-{range_match.group(2)}"
        else:
            time_match = re.search(r'(20\d{4})', query)
            if not time_match:
                time_match = re.search(r'(FY\d{2})', query, re.IGNORECASE)
            if time_match:
                new_time = time_match.group(1).upper()
        
        if new_time:
            extracted_time = new_time

        # 2b. Extract Scopes
        new_scopes = []

        explicit_scope_pairs = re.findall(r"\b(product|organization|tools|tool):([^\s]+)", query, flags=re.IGNORECASE)
        for cat, val in explicit_scope_pairs:
            cat = cat.lower()
            if cat == "tool":
                cat = "tools"
            val = val.strip()
            if val:
                new_scopes.append(f"{cat}:{val}")

        for prod in known_products:
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(prod)}(?![A-Za-z0-9_])", query, flags=re.IGNORECASE):
                new_scopes.append(f"product:{prod}")

        # Manual SN extraction (6 digits)
        # Avoid numbers starting with '20' if they look like the extracted time
        sn_matches = re.findall(r'\b(\d{6})\b', query)
        for sn in sn_matches:
            # If the 6-digit number is part of the extracted_time, skip it
            if extracted_time and sn in extracted_time:
                continue
            # If it starts with '20' and is likely a YYYYMM, skip it (unless we are sure it's an SN)
            if sn.startswith('20') and (202001 <= int(sn) <= 203012):
                continue
            new_scopes.append(f"tools:{sn}")

        # DB-assisted scope resolution for organization/tools (alphanumeric entities)
        try:
            kpi_def = kpi_definitions.get(matched_kpi) if matched_kpi else None
            table_name = (kpi_def or {}).get("table_name")
            scope_cols = (kpi_def or {}).get("scope_columns", {})
            org_col = scope_cols.get("organization")
            tools_col = scope_cols.get("tools")

            existing_orgs = {
                s.split(":", 1)[1]
                for s in (found_scopes + new_scopes)
                if s.startswith("organization:") and ":" in s
            }

            if db_service and table_name and (org_col or tools_col):
                raw_tokens = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]{1,49}", query)
                candidates: List[str] = []
                seen = set()
                for t in raw_tokens:
                    tt = t.strip()
                    if not tt:
                        continue
                    if tt.upper().startswith("FY") and re.fullmatch(r"FY\d{2,4}", tt.upper()):
                        continue
                    if re.fullmatch(r"20\d{4}", tt):
                        continue
                    if tt.upper() in known_products:
                        continue
                    if tt.lower() in {"kpi", "sql", "sn", "tool", "tools", "product", "organization"}:
                        continue
                    if tt not in seen:
                        seen.add(tt)
                        candidates.append(tt)
                candidates = candidates[:8]

                for token in candidates:
                    if org_col:
                        match = db_service.find_exact_match(table_name, org_col, token)
                        if match and match not in existing_orgs:
                            new_scopes.append(f"organization:{match}")
                            existing_orgs.add(match)

                    if tools_col:
                        match = db_service.find_exact_match(table_name, tools_col, token)
                        if match:
                            scope_str = f"tools:{match}"
                            if scope_str not in new_scopes and scope_str not in found_scopes:
                                new_scopes.append(scope_str)
        except Exception as e:
            print(f"DB-assisted scope resolution failed: {e}")

        # Update found_scopes
        if new_kpi and new_kpi != context_kpi:
            found_scopes = new_scopes
        else:
            for s in new_scopes:
                if s not in found_scopes:
                    found_scopes.append(s)

        # 4. AI Analysis (Improved for natural language scope)
        kpi_info = {k: v.get('description', '') for k, v in kpi_definitions.items()}
        all_categories = ui_mappings.get('scope_options', {}).get('categories', [])
        
        if matched_kpi and matched_kpi in kpi_definitions:
            allowed_scope_keys = list(kpi_definitions[matched_kpi].get('scope_columns', {}).keys())
            available_scopes = [s['value'] for s in all_categories if s['value'] in allowed_scope_keys]
        else:
            available_scopes = [s['value'] for s in all_categories]

        prompt = f"""
        [Role]
        你是一个专业的数据分析助手，负责从用户查询中提取关键参数。
        
        [Context]
        1. 当前已识别参数 (Current Context):
           - KPI: {matched_kpi}
           - Time Range: {extracted_time}
           - Scope: {json.dumps(found_scopes, ensure_ascii=False)}
        2. 可选指标 (Available KPIs): {json.dumps(kpi_info, ensure_ascii=False)}
        3. 可选维度分类 (Available Scopes categories): {available_scopes}
        4. 当前日期: {current_date.strftime('%Y-%m-%d')}
        
        [User Query]
        "{query}"
        
        [Instruction]
        基于当前上下文和用户新的查询，更新并提取 KPI、时间范围 (time_range) 和维度范围 (scope)。同时判断用户是否已经表达了“完成选择”或“不需要更多”的意图。
        
        [Rules]
        1. KPI 识别：如果上下文已有 KPI 且查询未明确更改，请保持现状。
        2. Scope 识别:
           - 识别具体的部门、团队、机台序列号。
           - 部门（如 "CT", "3DI", "SPS", "ES"）映射为 "product"。
           - 团队名称映射为 "organization"。
           - 机台 SN（如 100367）映射为 "tools"。
           - 格式必须为 "category:value"。
        3. 否定意图识别 (Negative Intent Recognition):
           - **重点**: 如果用户回答“没有”、“不用了”、“不需要”、“就这样”、“没了”、“所有”、“全部”、“跳过”等词汇，说明其不想再补充维度了。
           - 在这种情况下，JSON 必须返回 `"finished_selection": true`。
        4. 合并: 将新提取的内容与上下文合并。

        5. 时间范围识别:
           - 如果用户说“今年/本年”，按自然年转换为 "{current_year}01-{current_year}12"。
           - 如果用户说“去年”，按自然年转换为 "{current_year - 1}01-{current_year - 1}12"。
           - 如果用户说“明年”，按自然年转换为 "{current_year + 1}01-{current_year + 1}12"。
           - 自然时间示例："2024年" -> "202401-202412"；"202505" -> "202505"；"25年3月份" -> "202503"；"25年第三季度" -> "202507-202509"。
           - 财年示例（财年从4月到次年3月）："FY26" -> "202504-202603"；"FY26 2H" -> "202510-202603"。
           - 如果用户明确表达“不筛选时间/不限制时间/不限时间/所有范围/全部范围/所有时间/全部时间/all time/any time”，time_range 返回 "all"。
           - 兜底：如果用户只回复“所有/全部/不限/不限制/不限定”，且当前 time_range 为空，也视为 time_range="all"。
        
        [Output Format]
        Return JSON ONLY:
        {{
            "kpi": "kpi_key",
            "time_range": "time_value_or_null",
            "scope": ["category:value", ...],
            "finished_selection": true/false
        }}
        """
        print(f"Analyzing intent with context for: {query}")
        response_text = self.generate_response(prompt)
        
        result = {"kpi": matched_kpi, "time_range": extracted_time, "scope": found_scopes, "missing_params": [], "finished_selection": False}
        try:
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end != -1:
                ai_result = json.loads(response_text[start:end])
                if ai_result.get('kpi'): result['kpi'] = ai_result['kpi']
                if ai_result.get('time_range'): result['time_range'] = ai_result['time_range']
                if ai_result.get('scope'): 
                    result['scope'] = list(set(result.get('scope', []) + ai_result['scope']))
                if ai_result.get('finished_selection'):
                    result['finished_selection'] = True
        except: pass

        # --- Proactive Missing Params Logic ---
        missing = []
        
        # 1. Check Time
        if not result['time_range']: 
            missing.append('time_range')

        # 2. Check Scope
        negative_keywords = [
            "没有",
            "没",
            "没了",
            "不用",
            "不用了",
            "不需要",
            "不需要了",
            "不必",
            "无需",
            "就这样",
            "够了",
            "可以了",
            "跳过",
            "所有",
            "全部",
            "all",
            "nothing",
            "skip",
            "no",
            "none",
            "无",
        ]
        is_finished_selection = result['finished_selection'] or any(word in query_lower for word in negative_keywords)
        
        if is_finished_selection:
            result['finished_selection'] = True

        if result['kpi'] and result['kpi'] in kpi_definitions:
            kpi_def = kpi_definitions[result['kpi']]
            allowed = kpi_def.get('allowed_scopes', [])
            current_categories = set(s.split(':')[0] for s in result.get('scope', []) if ':' in s)
            missing_categories = [c for c in allowed if c not in current_categories]

            if not current_categories and not is_finished_selection:
                if scope_prompted:
                    result['finished_selection'] = True
                else:
                    missing.append('scope')
            elif current_categories and missing_categories and not is_finished_selection:
                if scope_prompted:
                    result['finished_selection'] = True
                else:
                    result['is_proactive_scope'] = True
                    result['missing_scope_categories'] = missing_categories
                    if 'scope' not in missing:
                        missing.append('scope')
        else:
            # KPI Unknown: We need context (Time + Scope/Finished) before we fail.
            has_scope = len(result.get('scope', [])) > 0
            if not has_scope and not is_finished_selection:
                if scope_prompted:
                    result['finished_selection'] = True
                else:
                    missing.append('scope')

        # 3. Handle KPI and Exception Logic
        if not result['kpi']:
            if missing:
                # If time or scope is missing, we ask for those first.
                pass 
            else:
                # Context is complete, but KPI is unknown -> Log and Error.
                if db_service:
                    db_service.log_exception(query, result['time_range'], result['scope'])
                
                result['response_message'] = "暂未支持这个KPI的开发，已收集这个问题，并告知项目负责人。"
                missing = []
                    
        result['missing_params'] = missing
        return result

    def _build_conditions_programmatically(self, kpi: str, time_range: str, scope: List[str], kpi_config: Dict) -> str:
        """Constructs WHERE clause conditions programmatically as a fallback."""
        kpi_def = kpi_config.get('kpi_definitions', {}).get(kpi, {})
        time_col = kpi_def.get('time_column', "")
        scope_cols = kpi_def.get('scope_columns', {})

        effective_time_col = 'st_Month' if time_col == 'st_FY' else time_col
        
        conditions = []
        
        # 1. Handle Time
        if time_range and str(time_range).strip().lower() == "all":
            pass
        elif time_range:
            if time_range.upper().startswith('FY'):
                try:
                    yy = time_range[2:]
                    fy_end_year = int(yy) if len(yy) == 4 else int(f"20{yy}")
                    start_year = fy_end_year - 1
                    conditions.append(
                        f"{effective_time_col} >= '{start_year}04' AND {effective_time_col} <= '{fy_end_year}03'"
                    )
                except Exception:
                    conditions.append(f"{effective_time_col} = '{time_range}'")
            elif '-' in time_range:
                start, end = time_range.split('-', 1)
                conditions.append(f"{effective_time_col} >= '{start}' AND {effective_time_col} <= '{end}'")
            else:
                conditions.append(f"{effective_time_col} = '{time_range}'")
        else:
            conditions.append(
                f"{effective_time_col} = (SELECT MAX({effective_time_col}) FROM {kpi_def.get('table_name')})"
            )
            
        # 2. Handle Scope
        if scope:
            # Group scope values by category
            scope_map = {}
            for s in scope:
                if ":" in s:
                    cat, val = s.split(":", 1)
                    if cat in scope_map:
                        scope_map[cat].append(val)
                    else:
                        scope_map[cat] = [val]
            
            for cat, values in scope_map.items():
                col = scope_cols.get(cat)
                if col:
                    if len(values) == 1:
                        conditions.append(f"{col} = '{values[0]}'")
                    else:
                        vals_str = ", ".join([f"'{v}'" for v in values])
                        conditions.append(f"{col} IN ({vals_str})")
        
        return " AND ".join(conditions)

    def generate_where_clause(self, kpi: str, time_range: str, scope: List[str], kpi_config: Dict) -> str:
        """Generates WHERE clause. Skips AI if parameters are clear to save time."""
        kpi_def = kpi_config.get('kpi_definitions', {}).get(kpi, {})
        if not kpi_def:
            return ""

        # Programmatic generation is much faster and reliable for clear params
        print(f"Generating conditions programmatically for {kpi}...")
        conditions = self._build_conditions_programmatically(kpi, time_range, scope, kpi_config)

        if not (conditions or "").strip():
            return ""
        
        if not conditions.upper().startswith("AND "):
            return f" AND {conditions}"
        return f" {conditions}"

    def generate_sql(self, kpi: str, time_range: str, scope: List[str], kpi_config: Dict) -> str:
        """Generates full SQL. Skips AI if parameters are clear to save time."""
        kpi_def = kpi_config.get('kpi_definitions', {}).get(kpi, {})
        template = kpi_def.get('sql_template', "")

        if not template:
            return ""

        print(f"Generating SQL programmatically for {kpi}...")

        def split_select_expressions(select_clause: str) -> List[str]:
            expressions = []
            current = []
            depth = 0
            quote = None
            for ch in select_clause:
                if quote:
                    current.append(ch)
                    if ch == quote:
                        quote = None
                    continue

                if ch in ("'", '"', '`'):
                    quote = ch
                    current.append(ch)
                    continue

                if ch == '(':
                    depth += 1
                    current.append(ch)
                    continue
                if ch == ')':
                    depth = max(0, depth - 1)
                    current.append(ch)
                    continue

                if ch == ',' and depth == 0:
                    expr = ''.join(current).strip()
                    if expr:
                        expressions.append(expr)
                    current = []
                    continue

                current.append(ch)

            last = ''.join(current).strip()
            if last:
                expressions.append(last)
            return expressions

        time_col = kpi_def.get('time_column')
        month_col = 'st_Month' if time_col == 'st_FY' else time_col
        if not month_col:
            return ""

        m = re.search(r"\bSELECT\b(?P<select>[\s\S]+?)\bFROM\b(?P<from>[\s\S]+)", template, flags=re.IGNORECASE)
        if not m:
            return ""

        select_clause = m.group('select').strip()
        from_clause = m.group('from').strip()

        value_exprs = split_select_expressions(select_clause)
        value_expr = value_exprs[0] if value_exprs else select_clause
        value_expr = re.sub(r"\s+AS\s+[`'\"]?[A-Za-z0-9_]+[`'\"]?\s*$", "", value_expr, flags=re.IGNORECASE)

        conditions = self._build_conditions_programmatically(kpi, time_range, scope, kpi_config)
        where_part = ""
        if conditions:
            where_part = f" AND {conditions}"

        base_sql = f"SELECT {month_col} AS month, {value_expr} AS value\nFROM {from_clause}"
        final_sql = base_sql.replace("{conditions}", where_part)
        final_sql += f"\nGROUP BY {month_col}\nORDER BY {month_col} ASC"

        print(f"Final SQL (Programmatic): {final_sql}")
        return final_sql



    def summarize_result(self, kpi: str, time_range: str, scope: List[str], data: Any, kpi_config: Dict) -> str:
        kpi_def = kpi_config.get('kpi_definitions', {}).get(kpi, {})
        # Use description directly but clean it up more aggressively if needed
        # Or just use the KPI name if description is too long/complex
        kpi_desc = kpi_def.get('description', kpi)
        
        # Split by comma or period to get the main title, avoiding formula details
        if "Keywords:" in kpi_desc:
            kpi_desc = kpi_desc.split("Keywords:")[0]
        
        kpi_desc = kpi_desc.split('。')[0].strip()
        
        scope_cols = kpi_def.get('scope_columns', {})
        
        # Reverse mapping for columns to friendly names
        col_to_label = {v: k.capitalize() for k, v in scope_cols.items()}
        # Common database columns to friendly names
        friendly_names = {
            "st_WrMonth": "月份",
            "st_Month": "月份",
            "st_DeptName": "产品组",
            "st_OrgName": "组织架构",
            "st_EmpNameCN": "姓名",
            "st_ProductLine": "产品线",
            "st_BU": "业务单元",
            "st_SN": "序列号",
            "st_EmpID": "工号",
            "st_ClassName": "岗位类别",
            "st_WorkLocation": "工作地点",
            "st_LEOName": "用工类型",
            "st_sn_org_teamname": "团队名称",
            "Hour": "总工时",
            "Sets": "总台数",
            "SUHourperTool": "平均每台装机工时",
            "total_startup_hours": "总Startup工时",
            "total_prewarranty_hours": "总Pre-warranty工时"
        }
        col_to_label.update(friendly_names)

        def get_friendly_name(col):
            if col in col_to_label:
                return col_to_label[col]
            if "COUNT" in col.upper():
                return "数量"
            return col

        # Programmatic summary for simple data to save time
        if isinstance(data, list):
            if len(data) == 0:
                return "当前系统中暂无相关数据。"


            if isinstance(data[0], dict) and set(data[0].keys()) >= {'month', 'value'} and len(data) > 1:
                table = f"为您查到以下 **{kpi_desc}** 统计结果：\n\n"
                table += f"| 月份 | {kpi_desc} |\n"
                table += "| --- | --- |\n"
                for row in data:
                    m = row.get('month', '')
                    v = row.get('value', '')
                    v_str = f"**{v}**" if isinstance(v, (int, float)) else str(v)
                    table += f"| {m} | {v_str} |\n"
                return table
            
            if len(data) == 1:
                row = data[0]
                if len(row) == 1:
                    val = list(row.values())[0]
                    return f"为您查到，{kpi_desc}的结果是：**{val}**。"
                else:
                    details = "，".join([f"{get_friendly_name(k)}为 {v}" for k, v in row.items()])
                    return f"为您查到：{details}。"

            # Multiple rows - Format as a Markdown Table
            columns = list(data[0].keys())
            friendly_cols = [get_friendly_name(c) for c in columns]
            
            # Header
            table = f"为您查到以下 **{kpi_desc}** 统计结果：\n\n"
            table += "| " + " | ".join(friendly_cols) + " |\n"
            table += "| " + " | ".join(["---"] * len(columns)) + " |\n"
            
            # Rows
            for row in data:
                # Format values (e.g. bold numbers)
                row_values = []
                for c in columns:
                    val = row.get(c, "")
                    if isinstance(val, (int, float)):
                        row_values.append(f"**{val}**")
                    else:
                        row_values.append(str(val))
                table += "| " + " | ".join(row_values) + " |\n"
            
            return table

        # Fallback to AI for very complex data if needed
        prompt = f"""
        [Task]
        Summarize the data result in a natural, friendly Chinese sentence. 
        
        [Context]
        KPI: {kpi_desc}
        Time: {time_range}
        Scope: {scope}
        Data Result: {json.dumps(data, ensure_ascii=False)}
        
        [Example]
        - "经查询，CT的FE人数是9人。"
        - "为您查到，202506月SPS部门的机台总数是120台。"
        - "当前系统中暂无相关数据。"
        
        [Rules]
        - Be concise.
        - Use Chinese only.
        - Do not show internal IDs or JSON structures.
        """
        print(f"Summarizing result for {kpi}...")
        summary = self.generate_response(prompt).strip()
        
        # Clean up <think> tags if present
        if "</think>" in summary:
            summary = summary.split("</think>")[-1].strip()
            
        return summary or "查询完成。"
