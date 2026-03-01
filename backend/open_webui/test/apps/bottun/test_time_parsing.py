import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from open_webui.apps.bottun.services import AIService


def _expected_prev_fy_range(now: datetime) -> str:
    fy_start_year = now.year if now.month >= 4 else now.year - 1
    fy_end_year = fy_start_year + 1
    prev_fy_start_year = fy_start_year - 1
    prev_fy_end_year = fy_end_year - 1
    return f"{prev_fy_start_year}04-{prev_fy_end_year}03"


def _expected_current_fy_range(now: datetime) -> str:
    fy_start_year = now.year if now.month >= 4 else now.year - 1
    fy_end_year = fy_start_year + 1
    return f"{fy_start_year}04-{fy_end_year}03"


def _current_fy_end_year(now: datetime) -> int:
    fy_start_year = now.year if now.month >= 4 else now.year - 1
    return fy_start_year + 1


def _fiscal_half_range(fy_end_year: int, half: int) -> str:
    start_year = fy_end_year - 1
    if half == 1:
        return f"{start_year}04-{start_year}09"
    return f"{start_year}10-{fy_end_year}03"


def _current_fiscal_half(now: datetime) -> tuple[int, int]:
    return _current_fy_end_year(now), (1 if 4 <= now.month <= 9 else 2)


def _prev_fiscal_half(fy_end_year: int, half: int) -> tuple[int, int]:
    if half == 2:
        return fy_end_year, 1
    return fy_end_year - 1, 2


def _shift_fiscal_half_back(fy_end_year: int, half: int, steps: int) -> tuple[int, int]:
    fy = fy_end_year
    h = half
    for _ in range(max(0, steps)):
        fy, h = _prev_fiscal_half(fy, h)
    return fy, h


def _fiscal_year_range(fy_end_year: int) -> str:
    return f"{fy_end_year - 1}04-{fy_end_year}03"



def _minimal_kpi_config():
    return {
        "kpi_definitions": {
            "su_hour_per_tool": {
                "description": "",
                "scope_columns": {},
            }
        },
    }


def test_time_parsing_last_fiscal_year_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()

    result = service.analyze_intent(
        "上个财年的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == _expected_prev_fy_range(now)


def test_time_parsing_current_fiscal_year_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()

    result = service.analyze_intent(
        "本财年的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == _expected_current_fy_range(now)


def test_time_parsing_last_fiscal_half_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()
    cur_fy, cur_h = _current_fiscal_half(now)
    prev_fy, prev_h = _prev_fiscal_half(cur_fy, cur_h)

    result = service.analyze_intent(
        "上个半期的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == _fiscal_half_range(prev_fy, prev_h)


def test_time_parsing_prev_three_halves_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()
    cur_fy, cur_h = _current_fiscal_half(now)
    end_fy, end_h = _shift_fiscal_half_back(cur_fy, cur_h, 1)
    start_fy, start_h = _shift_fiscal_half_back(cur_fy, cur_h, 3)
    start_ym = _fiscal_half_range(start_fy, start_h).split("-", 1)[0]
    end_ym = _fiscal_half_range(end_fy, end_h).split("-", 1)[1]

    result = service.analyze_intent(
        "前三个半期的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == f"{start_ym}-{end_ym}"


def test_time_parsing_prev_two_halves_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()
    cur_fy, cur_h = _current_fiscal_half(now)
    end_fy, end_h = _shift_fiscal_half_back(cur_fy, cur_h, 1)
    start_fy, start_h = _shift_fiscal_half_back(cur_fy, cur_h, 2)
    start_ym = _fiscal_half_range(start_fy, start_h).split("-", 1)[0]
    end_ym = _fiscal_half_range(end_fy, end_h).split("-", 1)[1]

    result = service.analyze_intent(
        "前2个半期的su hour per tool是多少",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == f"{start_ym}-{end_ym}"


def test_time_parsing_prev_three_fiscal_years_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()
    cur_fy_end = _current_fy_end_year(now)
    start_fy_end = cur_fy_end - 2
    start_ym = _fiscal_year_range(start_fy_end).split("-", 1)[0]
    end_ym = _fiscal_year_range(cur_fy_end).split("-", 1)[1]

    result = service.analyze_intent(
        "前三个财年的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == f"{start_ym}-{end_ym}"


def test_time_parsing_prev_six_fiscal_years_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")
    now = datetime.now()
    cur_fy_end = _current_fy_end_year(now)
    start_fy_end = cur_fy_end - 5
    start_ym = _fiscal_year_range(start_fy_end).split("-", 1)[0]
    end_ym = _fiscal_year_range(cur_fy_end).split("-", 1)[1]

    result = service.analyze_intent(
        "我想查询前6个财年的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == f"{start_ym}-{end_ym}"


def test_time_parsing_all_time_cn():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "全部的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == "all"


def test_time_parsing_natural_quarter_compact():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "2026Q1的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == "202601-202603"


def test_time_parsing_invalid_month_prompts():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "2025-13的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={},
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] is None
    assert "time_range" in (result.get("missing_params") or [])
    assert "时间格式" in (result.get("response_message") or "")


def test_scope_fallback_all_after_prompted():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "东京的su hour per tool",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={
            "kpi": "su_hour_per_tool",
            "time_range": "202501-202506",
            "scope": [],
            "scope_prompted": True,
        },
        db_service=None,
    )

    assert result["kpi"] == "su_hour_per_tool"
    assert result["time_range"] == "202501-202506"
    assert result.get("scope") == []
    assert result.get("scope_fallback_all") is True
    assert result.get("missing_params") == []
    assert result.get("finished_selection") is True


def test_unsupported_kpi_prompt_wording_when_context_incomplete():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "NUE",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={"kpi": "NUE", "time_range": None, "scope": [], "unsupported_kpi_notified": False},
        db_service=None,
    )

    assert result.get("unsupported_kpi") is True
    assert result.get("missing_params") == ["time_range"]
    assert "暂未上线这个指标。我们希望完整收集您的需求并同步给负责人。" in (result.get("response_message") or "")


def test_unsupported_kpi_received_wording_when_context_complete():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "补充",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={
            "kpi": "NUE",
            "time_range": "202601-202612",
            "scope": ["product:TPS"],
            "unsupported_kpi_notified": False,
        },
        db_service=None,
    )

    assert result.get("unsupported_kpi") is True
    assert result.get("missing_params") == []
    assert "暂未上线这个指标，已收到补充信息：" in (result.get("response_message") or "")


def test_unsupported_kpi_all_does_not_override_time_range():
    os.environ["BOTTUN_ENABLE_LLM_INTENT"] = "false"
    service = AIService(model="qwen", base_url="http://localhost:11434/v1")

    result = service.analyze_intent(
        "所有",
        _minimal_kpi_config(),
        {"scope_options": {"categories": []}},
        context={
            "kpi": "NUE",
            "time_range": "202601-202612",
            "scope": [],
            "scope_prompted": True,
            "unsupported_kpi_notified": True,
        },
        db_service=None,
    )

    assert result.get("unsupported_kpi") is True
    assert result.get("time_range") == "202601-202612"
