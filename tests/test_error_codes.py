"""
창구② 에러코드 사전 조회 시험 — docs/specs/error-codes.md 의 AC 를 그대로 옮긴 것.
"""

import pytest

from mcp_server.server import get_error_code_info
from mcp_server.tools.data_loader import load_error_codes
from mcp_server.tools.error_codes import lookup_error_codes


def test_ac01_정상_코드_조회():
    """AC-01: E-102, M-204 의 보통 정지시간과 심각도"""
    r = lookup_error_codes(["E-102", "M-204"])
    assert r["found_count"] == 2

    e102, m204 = r["results"]            # 결과 2개를 순서대로 꺼내기
    assert (e102["typical_min"], e102["typical_max"], e102["severity_hint"]) == (10.0, 30.0, "보통")
    assert (m204["typical_min"], m204["typical_max"], m204["severity_hint"]) == (90.0, 240.0, "중대")


def test_ac02_없는_코드와_빈_코드():
    """AC-02: 사전에 없는 코드·빈 코드는 found=False 이고, 원인 정보를 주지 않는다"""
    r = lookup_error_codes(["E-102", "X-999", ""])
    assert r["requested_count"] == 3
    assert r["found_count"] == 1
    assert r["not_found_codes"] == ["X-999", ""]

    for item in r["results"][1:]:        # [1:] = 첫 번째(E-102)를 빼고 나머지
        assert item["found"] is False
        assert "message" in item
        # 원인을 지어낼 재료가 없어야 한다
        assert "category" not in item
        assert "typical_cause" not in item


def test_ac03_특수_코드_표시():
    """AC-03: ETC-602 는 계획 정지, ETC-604 는 원인 미확인"""
    etc602, etc604 = lookup_error_codes(["ETC-602", "ETC-604"])["results"]
    assert etc602["is_planned_stop"] is True
    assert etc604["is_unknown_cause"] is True


def test_ac04_입력_정리():
    """AC-04: 소문자·공백·중복이 섞여도 한 번만 조회"""
    r = lookup_error_codes([" e-102 ", "E-102"])
    assert r["requested_count"] == 1
    assert r["results"][0]["error_code"] == "E-102"


def test_ac05_글자_하나_입력():
    """AC-05: 목록 대신 글자 하나만 넣어도 동작"""
    assert lookup_error_codes("S-303")["found_count"] == 1


def test_ac06_사전_전체_숫자_변환():
    """AC-06: 사전 24개 코드 모두 보통 정지시간이 숫자로 바뀐다"""
    codes = list(load_error_codes()["error_code"])
    r = lookup_error_codes(codes)
    assert r["found_count"] == len(codes) == 24
    for item in r["results"]:
        assert item["typical_min"] is not None
        assert item["typical_max"] is not None
        assert item["typical_min"] <= item["typical_max"]


# 서로 다른 코드 51개 만들기: ["C-0", "C-1", ..., "C-50"]
TOO_MANY = [f"C-{i}" for i in range(51)]


@pytest.mark.parametrize("bad", [[], TOO_MANY], ids=["빈_목록", "51개"])
def test_ac07_입력_오류(bad):
    """AC-07: 함수는 ValueError, MCP 도구는 error/hint dict"""
    with pytest.raises(ValueError):
        lookup_error_codes(bad)

    result = get_error_code_info(bad)
    assert "error" in result and "hint" in result
