"""유사 문장 검색 실측 — CSV 데이터가 있을 때만 실행.

실행: MESTORY_DATA_DIR=docs python -m pytest tests/test_semantic_data.py -q
데이터가 없으면 conftest가 자동으로 skip한다 (no_data 표시 없음).
"""

from mcp_server.tools.semantic import (
    search_error_descriptions,
    search_maintenance_actions,
    search_operator_notes,
)


def test_메모검색_결과계약():
    out = search_operator_notes("정비팀 호출", top_k=3)
    assert out["query"] == "정비팀 호출"
    assert out["backend"] == "tfidf"
    assert out["total_candidates"] > 0
    for hit in out["results"]:
        assert 0.0 <= hit["score"] <= 1.0
        assert hit["log_id"].startswith("LOG-")
        assert hit["operator_note"].strip() != ""


def test_메모검색_설비필터():
    out = search_operator_notes("점검", top_k=5, equipment_id="EQ-001")
    assert out["total_candidates"] >= 0
    for hit in out["results"]:
        assert hit["equipment_id"] == "EQ-001"


def test_정비검색_결과계약():
    out = search_maintenance_actions("볼트 조임", top_k=3)
    assert out["returned_count"] >= 1
    top = out["results"][0]
    assert top["maintenance_id"].startswith("MT-")
    assert "볼트" in (top["action_taken"] + top["result"])


def test_에러설명검색_서보모터():
    out = search_error_descriptions("서보모터 과전류", top_k=3)
    assert out["returned_count"] >= 1
    assert out["results"][0]["error_code"] == "E-102"


def test_에러설명검색_결과는_후보일뿐():
    # 설명문 검색이 코드를 "확정"하지 않음을 계약으로 고정한다.
    # 최종 판정은 lookup_error_codes(exact) 몫이다.
    out = search_error_descriptions("전류가 많이 흐름", top_k=3)
    assert "needs_review" in out and "review_reason" in out
    for hit in out["results"]:
        assert "score" in hit and "error_code" in hit


def test_무관질의는_needs_review():
    out = search_error_descriptions("우주선 발사 실패", top_k=3, threshold=0.5)
    assert out["needs_review"] is True
