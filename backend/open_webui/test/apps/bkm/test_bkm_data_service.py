import json


from open_webui.apps.bkm.services import BkmDataService


def test_bkm_data_service_load_and_search(tmp_path):
    data = [
        {
            "id": "1",
            "title": "Vacuum error",
            "question": "Vacuum alarm occurs during process",
            "pairs": [
                {
                    "action": "Check pump",
                    "root_cause": "Pump degraded",
                    "evidence": "Pump pressure unstable",
                    "data_source": {"pdf": "bkm.pdf", "page": 12},
                }
            ],
        },
        {
            "id": "2",
            "title": "Temperature drift",
            "question": "Temperature not stable",
            "pairs": [
                {
                    "action": "Calibrate sensor",
                    "root_cause": "Sensor offset",
                    "data_source": {"pdf": "bkm.pdf", "pages": [8, 9]},
                }
            ],
        },
    ]
    p = tmp_path / "bkm.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    svc = BkmDataService(json_path=str(p))
    status = svc.status()
    assert status["items"] == 2

    items = svc.search("vacuum pump", top_k=3)
    assert len(items) >= 1
    assert items[0]["id"] == "1"
    assert items[0]["pairs"][0]["action"] == "Check pump"


def test_bkm_data_service_compose_answer_with_references(tmp_path):
    data = {
        "items": [
            {
                "id": "a",
                "问题描述": "Leak detected",
                "对应action": ["Tighten fitting"],
                "对应root cause": ["Loose connection"],
                "data source": {"pdf_name": "manual.pdf", "page": "15"},
            }
        ]
    }
    p = tmp_path / "bkm.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    svc = BkmDataService(json_path=str(p))
    out = svc.compose_answer("leak", top_k=5)
    assert out["items"]
    assert out["references"] == [{"pdf": "manual.pdf", "page": 15}]
    assert "Action" in out["answer_markdown"]
    assert "Root Cause" in out["answer_markdown"]

