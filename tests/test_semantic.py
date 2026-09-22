"""유사 문장 검색(시맨틱-lite) — 안전선 검증.

배경: mcp_server/tools/semantic.py는 exact 조회(창구 ①②③)의 보조다.
ID·코드의 동일성을 판단하지 않으며, 결과는 점수+원문+ID를 함께 돌려준다.
아래 시험은 데이터 없이도 도는 계약 시험(no_data)과, CSV가 있을 때만 도는
실측 시험으로 나뉜다.
"""

import pytest

from mcp_server.tools import semantic
from mcp_server.tools.semantic import (
    _needs_review,
    _rank_texts,
    get_backend_name,
)

pytestmark = pytest.mark.no_data


def test_백엔드_기본값은_tfidf():
    assert get_backend_name() == "tfidf"


def test_백엔드_잘못된값은_에러(monkeypatch):
    monkeypatch.setenv("MESTORY_SEMANTIC_BACKEND", "bert")
    with pytest.raises(RuntimeError):
        get_backend_name()


def test_빈질의는_에러():
    with pytest.raises(ValueError):
        semantic.search_operator_notes("")
    with pytest.raises(ValueError):
        semantic.search_maintenance_actions("  ")
    with pytest.raises(ValueError):
        semantic.search_error_descriptions("")


def test_순위_점수순_임계값미만제외():
    texts = ["베어링 소음으로 정지", "컨베이어 벨트 이탈", "베어링 진동으로 정지"]
    ranked = _rank_texts("베어링 소음", texts, top_k=5, threshold=0.0, backend="tfidf")
    assert ranked, "무관 문장까지 포함하면 0건이면 안 된다(threshold=0.0)"
    # 1위는 질의와 같은 단어를 가진 문서여야 한다
    assert ranked[0][0] == 0
    assert all(0.0 <= s <= 1.0 for _, s in ranked)


def test_임계값_높으면_빈결과():
    texts = ["베어링 소음으로 정지", "컨베이어 벨트 이탈"]
    ranked = _rank_texts("베어링 소음", texts, top_k=5, threshold=0.99, backend="tfidf")
    assert ranked == []


def test_needs_review_0건이면_참():
    needs, reason = _needs_review([], 0.12)
    assert needs is True and reason


def test_needs_review_확실하면_거짓():
    needs, _ = _needs_review([0.8, 0.2], 0.12)
    assert needs is False


def test_needs_review_1위낮으면_참():
    needs, _ = _needs_review([0.15], 0.12)
    assert needs is True


def test_needs_review_12위박빙이면_참():
    needs, _ = _needs_review([0.30, 0.29], 0.12)
    assert needs is True
