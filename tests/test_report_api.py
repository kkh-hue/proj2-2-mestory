"""리포트 연결 AC: 실제 LLM/DB/MCP 호출 없이 CORS와 HTTP 계약 검증."""

import importlib.util
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.no_data


@pytest.fixture
def api(monkeypatch):
    def load(origins=None):
        if origins is None:
            monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)
        else:
            monkeypatch.setenv("CORS_ALLOWED_ORIGINS", origins)
        # 본래 모듈을 reload하지 않아 다른 테스트의 앱/환경에 영향을 주지 않는다.
        path = Path(__file__).resolve().parents[1] / "backend" / "main.py"
        spec = importlib.util.spec_from_file_location("backend._report_api_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        generator = AsyncMock(side_effect=AssertionError("LLM 호출은 모의 처리해야 합니다"))
        monkeypatch.setattr(module, "generate_report", generator)
        monkeypatch.setattr(module, "get_model_name", lambda: "test-model")
        # 설비 마스터 조회도 모의한다. 안 하면 DB·CSV가 없는 환경에서 503이 나 422 검증까지 못 간다.
        monkeypatch.setattr(
            module, "_load_equipment_master",
            AsyncMock(return_value=({"EQ-001": "LINE-A", "EQ-004": "LINE-A", "EQ-057": "LINE-C"}, {"EQ-001": "사출성형기", "EQ-004": "사출성형기", "EQ-057": "컨베이어"})),
        )
        return module, generator

    return load


def preflight(client, origin, method="POST"):
    return client.options("/report", headers={
        "Origin": origin,
        "Access-Control-Request-Method": method,
        "Access-Control-Request-Headers": "content-type",
    })


@pytest.mark.parametrize("setting,origin", [
    (None, "http://localhost:3000"),
    (" https://mestory-app.up.railway.app, , http://localhost:3000, ",
     "https://mestory-app.up.railway.app"),
    (" https://mestory-app.up.railway.app, , http://localhost:3000, ",
     "http://localhost:3000"),
])
def test_allowed_preflight(api, setting, origin):
    module, generator = api(setting)
    with TestClient(module.app) as client:
        response = preflight(client, origin)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "content-type" in response.headers["access-control-allow-headers"].lower()
    assert "access-control-allow-credentials" not in response.headers
    generator.assert_not_awaited()


@pytest.mark.parametrize("setting,origin", [
    (None, "https://unlisted.example"),
    ("https://mestory-app.up.railway.app", "http://localhost:3000"),
    ("", "http://localhost:3000"),
])
def test_disallowed_origin(api, setting, origin):
    module, generator = api(setting)
    with TestClient(module.app) as client:
        response = preflight(client, origin)
    assert response.status_code == 400
    assert "access-control-allow-origin" not in response.headers
    generator.assert_not_awaited()


def test_disallowed_method(api):
    module, generator = api()
    with TestClient(module.app) as client:
        response = preflight(client, "http://localhost:3000", "DELETE")
    assert response.status_code == 400
    generator.assert_not_awaited()


@pytest.mark.parametrize("payload", [
    {"line_id": "LINE-A", "equipment_id": "EQ-004", "date_from": "2026-01-03",
     "date_to": "2026-01-03", "session_id": "session-1"},
])
def test_report_contract(api, payload):
    module, generator = api()
    expected = {
        "equipment_id": "EQ-004", "line_id": "LINE-A", "period": "2026-01-03 ~ 2026-01-03",
        "causes": [{"error_code": "E-102", "description": "시험 원인", "severity": "보통",
                    "evidence": "시험 근거", "is_confirmed": False}],
        "unclassified_count": 0, "confidence_note": "시험 응답", "recommended_action": "확인 필요",
        # 멀티모달로 늘어난 칸 2개 (docs/specs/multimodal.md).
        # 이미지를 안 보낸 요청이므로 기본값 그대로 나와야 한다.
        "visual_findings": None, "used_image": False,
    }
    generator.side_effect = None
    generator.return_value = module.DowntimeReport(**expected)
    with TestClient(module.app) as client:
        response = client.post("/report", json=payload, headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.json() == expected
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"

    generator.assert_awaited_once()
    call_kwargs = dict(generator.call_args.kwargs)
    # report_id는 요청마다 새로 만드는 UUID라 값을 미리 알 수 없다 — 형태만 확인하고,
    # 응답 헤더(X-Report-Id)로 프론트에 그대로 전달됐는지를 대신 확인한다.
    report_id = call_kwargs.pop("report_id")
    assert response.headers["x-report-id"] == report_id
    assert call_kwargs == {
        field: payload.get(field)
        for field in ("line_id", "equipment_id", "date_from", "date_to", "session_id", "images", "message")
    }


@pytest.mark.parametrize("field,value", [
    ("date_from", "2026-99-99"),
    ("date_to", "abc"),
    ("date_from", "2026/09/20"),
    ("date_from", "2026-02-30"),  # 형식은 맞지만 없는 날짜
    ("date_to", "2026-9-1"),      # 0 채우기 없음
    ("date_from", "20260901"),    # 구분자 없는 ISO 기본 형식
])
def test_invalid_report_date_is_rejected_before_llm(api, field, value):
    module, generator = api()
    payload = {"line_id": "LINE-A", field: value}

    with TestClient(module.app) as client:
        response = client.post("/report", json=payload)

    assert response.status_code == 422
    assert "날짜는 YYYY-MM-DD 형식이어야 합니다." in response.json()["detail"][0]["msg"]
    generator.assert_not_awaited()


def test_report_date_range_is_rejected_before_llm(api):
    module, generator = api()

    with TestClient(module.app) as client:
        response = client.post(
            "/report",
            json={"line_id": "LINE-A", "date_from": "2026-09-20", "date_to": "2026-09-10"},
        )

    assert response.status_code == 422
    assert "date_from은 date_to보다 늦을 수 없습니다." in response.json()["detail"][0]["msg"]
    generator.assert_not_awaited()


def test_api_agent_uses_the_same_report_date_validation(api):
    module, generator = api()

    with TestClient(module.app) as client:
        response = client.post("/api/agent", json={"line_id": "LINE-A", "date_to": "2026/09/20"})

    assert response.status_code == 422
    generator.assert_not_awaited()


def test_report_analysis_infrastructure_failure_returns_503_without_report_id(api):
    module, generator = api()
    generator.side_effect = module.AnalysisInfrastructureError("분석 인프라에 연결할 수 없습니다")

    with TestClient(module.app) as client:
        response = client.post("/report", json={"line_id": "LINE-A"})

    assert response.status_code == 503
    assert response.json() == {"detail": "분석 인프라에 연결할 수 없습니다"}
    assert "x-report-id" not in response.headers


@pytest.mark.parametrize("failure", ["report", "message"])
def test_report_storage_failure_returns_503_without_report_id(api, failure):
    module, generator = api()
    generator.side_effect = module.DatabaseUnavailableError(f"{failure} storage failed")

    with TestClient(module.app) as client:
        response = client.post("/report", json={"line_id": "LINE-A"})

    assert response.status_code == 503
    assert response.json() == {"detail": f"{failure} storage failed"}
    assert "x-report-id" not in response.headers


def test_report_db_failure_returns_503(api, monkeypatch):
    module, generator = api()
    monkeypatch.setattr(
        module,
        "get_session_scope",
        AsyncMock(side_effect=module.DatabaseUnavailableError("DB unavailable")),
    )

    with TestClient(module.app) as client:
        response = client.post("/report", json={"message": "분석", "session_id": "session-1"})

    assert response.status_code == 503
    assert response.json() == {"detail": "DB unavailable"}
    assert "x-report-id" not in response.headers
    generator.assert_not_awaited()


def test_empty_report_list_keeps_success_response(api, monkeypatch):
    module, _ = api()
    monkeypatch.setattr(module, "list_reports", AsyncMock(return_value=[]))

    with TestClient(module.app) as client:
        response = client.get("/reports")

    assert response.status_code == 200
    assert response.json() == []


def test_report_not_found_keeps_404_when_db_is_healthy(api, monkeypatch):
    module, _ = api()
    monkeypatch.setattr(module, "get_report", AsyncMock(return_value=None))

    with TestClient(module.app) as client:
        response = client.get("/reports/missing")

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("path", "function_name"),
    [
        ("/chat/sessions", "list_chat_sessions"),
        ("/chat/session-1", "list_chat_turns"),
        ("/dashboard", "get_dashboard_summary"),
        ("/downtime/analysis", "get_downtime_analysis"),
        ("/alerts", "list_alerts"),
        ("/equipment", "list_equipment_status"),
    ],
)
def test_db_failure_returns_503_for_read_apis(api, monkeypatch, path, function_name):
    module, _ = api()
    monkeypatch.setattr(
        module,
        function_name,
        AsyncMock(side_effect=module.DatabaseUnavailableError("DB unavailable")),
    )

    with TestClient(module.app) as client:
        response = client.get(path)

    assert response.status_code == 503
    assert response.json() == {"detail": "DB unavailable"}


def test_invalid_request_keeps_422(api):
    module, generator = api()
    with TestClient(module.app) as client:
        response = client.post("/report", json={"line_id": []})
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "line_id"]
    generator.assert_not_awaited()


def test_report_scope_ac06_질문에_범위가_없으면_422이고_생성하지_않는다(api):
    module, generator = api()
    # DB가 정상이고 범위만 없는 경우의 422를 검증한다.
    module.get_session_scope = AsyncMock(return_value=None)
    with TestClient(module.app) as client:
        response = client.post("/report", json={"message": "원인 분석해줘", "session_id": "s-1"})
    assert response.status_code == 422
    assert "설비" in response.json()["detail"]
    generator.assert_not_awaited()


def test_report_scope_ac01_질문_속_설비가_조건으로_넘어간다(api, monkeypatch):
    module, generator = api()
    monkeypatch.setattr(module, "_load_equipment_master", AsyncMock(return_value=({"EQ-057": "LINE-C"}, {"EQ-057": "컨베이어"})))
    monkeypatch.setattr(module, "get_session_scope", AsyncMock(return_value=None))
    generator.side_effect = None
    generator.return_value = module.DowntimeReport(
        equipment_id="EQ-057", line_id="LINE-C", period="전체 ~ 전체", causes=[], unclassified_count=0,
        confidence_note="", recommended_action="",
    )
    with TestClient(module.app) as client:
        response = client.post("/report", json={"message": "EQ-057 원인 분석해줘", "session_id": "s-1"})
    assert response.status_code == 200
    kwargs = generator.call_args.kwargs
    assert (kwargs["line_id"], kwargs["equipment_id"]) == ("LINE-C", "EQ-057")


def test_report_scope_rejects_equipment_line_mismatch_before_llm(api, monkeypatch):
    module, generator = api()
    monkeypatch.setattr(module, "_load_equipment_master", AsyncMock(return_value=({"EQ-057": "LINE-C"}, {"EQ-057": "컨베이어"})))

    with TestClient(module.app) as client:
        response = client.post("/report", json={"line_id": "LINE-A", "equipment_id": "EQ-057"})

    assert response.status_code == 422
    assert "x-report-id" not in response.headers
    generator.assert_not_awaited()


def test_report_scope_rejects_master_lookup_failure(api, monkeypatch):
    module, generator = api()
    monkeypatch.setattr(
        module,
        "_load_equipment_master",
        AsyncMock(side_effect=module.DatabaseUnavailableError("master unavailable")),
    )

    with TestClient(module.app) as client:
        response = client.post("/report", json={"equipment_id": "EQ-057"})

    assert response.status_code == 503
    assert response.json() == {"detail": "master unavailable"}
    assert "x-report-id" not in response.headers
    generator.assert_not_awaited()


@pytest.mark.parametrize("payload", [{}, {"line_id": None, "equipment_id": None, "date_from": None, "date_to": None, "session_id": None}])
def test_report_scope_ac10_범위가_전혀_없으면_message가_없어도_422(api, payload):
    module, generator = api()
    with TestClient(module.app) as client:
        response = client.post("/report", json=payload)
    assert response.status_code == 422
    assert "설비" in response.json()["detail"]
    generator.assert_not_awaited()
