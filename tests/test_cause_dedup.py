"""원인(causes) 목록 중복 제거 — DB·LLM 없이 순수 함수만 검증.

배경: 에이전트가 도구를 여러 번 왕복하며 같은 에러코드의 원인을 표현만 바꿔
두 번 적는 경우가 있다. 검색 결과를 프롬프트에 넣는 게 아니라 LLM 출력을 받은
뒤의 후처리이므로 RAG가 아니고, 문자열 유사도(difflib)만 쓰므로 임베딩도 아니다.

기준값(0.97)이 왜 이렇게 높은지는 backend/services/llm.py의 _CAUSE_DEDUP_RATIO
주석 참고 — 짧은 한국어 기술 문장은 핵심 단어 한두 글자만 달라도(예: "온도"↔"진동")
전체 유사도는 오히려 높게 나올 수 있어, 낮은 기준값은 서로 다른 원인을 지워버리는
위험한 오탐을 만든다. 아래 test_핵심_단어만_다르면_유사도가_높아도_지우지_않는다가
그 위험을 직접 재현해 막아 준다.
"""

import pytest

from backend.services.llm import DowntimeCause, _dedupe_causes

pytestmark = pytest.mark.no_data


def _cause(code: str, description: str, *, severity: str = "보통", confirmed: bool = True) -> DowntimeCause:
    return DowntimeCause(
        error_code=code, description=description, severity=severity,
        evidence="근거", is_confirmed=confirmed,
    )


def test_같은_코드에_거의_완전히_같은_문장은_하나만_남는다():
    causes = [
        _cause("S-301", "온도 센서 값 이상으로 설비가 정지됨"),
        _cause("S-301", "온도 센서 값 이상으로 설비가 정지됨."),  # 마침표만 다름
    ]
    result = _dedupe_causes(causes)
    assert len(result) == 1
    assert result[0] is causes[0]  # 먼저 나온 것을 남긴다


def test_같은_코드라도_풀어_쓴_정도로만_다르면_둘_다_남는다():
    # 유사도 0.79 수준 — 기준값(0.97)에 한참 못 미쳐 지우지 않는다.
    # 표현이 다른 진짜 중복을 놓칠 수 있지만, 그게 안전한 쪽이다(주석 참고).
    causes = [
        _cause("S-301", "온도 센서 값 이상으로 설비가 정지됨"),
        _cause("S-301", "온도 센서 값이 이상하여 설비가 정지되었음"),
    ]
    assert _dedupe_causes(causes) == causes


def test_핵심_단어만_다르면_유사도가_높아도_지우지_않는다():
    # ⚠️ 회귀 방지의 핵심 테스트. "온도"↔"진동"만 바뀐 문장은 문자열 유사도가 0.9로
    # 높게 나오지만(위 "풀어 쓴" 케이스의 0.79보다 오히려 높다), 실제로는 전혀 다른
    # 원인이다. 기준값이 낮았다면 이 두 원인이 하나로 지워졌을 것이다.
    causes = [
        _cause("S-301", "온도 센서 값 이상으로 설비가 정지됨"),
        _cause("S-301", "진동 센서 값 이상으로 설비가 정지됨"),
    ]
    assert _dedupe_causes(causes) == causes


def test_코드가_다르면_문장이_같아도_합치지_않는다():
    causes = [
        _cause("E-102", "서보모터 과전류로 정지"),
        _cause("E-104", "서보모터 과전류로 정지"),
    ]
    assert _dedupe_causes(causes) == causes


def test_코드가_비어있으면_묶지_않는다():
    # 미등록·데이터 오류 등으로 error_code가 없는 건은 서로 무관할 수 있어 지우지 않는다.
    causes = [
        _cause("", "원인 미확인 — 현장 확인 필요"),
        _cause("", "원인 미확인 — 현장 확인 필요"),
    ]
    assert _dedupe_causes(causes) == causes


def test_세_건_중_거의_동일한_두_건만_지운다():
    causes = [
        _cause("SW-501", "소프트웨어 오류로 설비 정지"),
        _cause("SW-501", "소프트웨어 오류로 설비 정지 "),  # 끝 공백만 다름 → 중복 처리
        _cause("SW-501", "PLC 통신 지연으로 재발 가능성 있음"),  # 전혀 다른 문장 → 유지
    ]
    result = _dedupe_causes(causes)
    assert result == [causes[0], causes[2]]


def test_빈_목록은_그대로_빈_목록():
    assert _dedupe_causes([]) == []
