"""p95 계산 — scripts/latency_stats.py

옛 계산 s[min(len(s)-1, int(len(s)*0.95))]는 10건이면 최댓값, 30건이면 뒤에서 두 번째를 돌려줬다.
새 계산은 정렬한 값 사이를 선형보간한다: 위치 = (건수 - 1) × 0.95 (0부터 센 순번).
기대값은 모두 손으로 계산해 각 시험의 주석에 적었다.
"""

import pytest

from scripts.latency_stats import p95

# 이 파일의 시험은 CSV/DB 데이터가 없어도 돌아간다 (conftest.py의 no_data 표시).
pytestmark = pytest.mark.no_data


def test_10건이면_최댓값이_아니라_보간한_값이다():
    # ① 1~10 (10개)
    #    위치 = (10 - 1) × 0.95 = 8.55
    #    → 0부터 센 8번째(9)와 9번째(10) 사이에서 55% 지점 = 9 + 0.55 × (10 - 9) = 9.55
    #    옛 계산: int(10 × 0.95) = 9 → s[9] = 10 (최댓값)
    latencies = list(range(1, 11))
    assert p95(latencies) == pytest.approx(9.55)
    assert p95(latencies) < max(latencies)


def test_30건이면_뒤에서_두_번째가_아니라_보간한_값이다():
    # ② 1~30 (30개)
    #    위치 = (30 - 1) × 0.95 = 27.55
    #    → 0부터 센 27번째(28)와 28번째(29) 사이에서 55% 지점 = 28 + 0.55 × (29 - 28) = 28.55
    #    옛 계산: int(30 × 0.95) = 28 → s[28] = 29 (뒤에서 두 번째) — 건수만 늘려서는 안 고쳐졌다
    latencies = list(range(1, 31))
    assert p95(latencies) == pytest.approx(28.55)


def test_입력_순서와_상관없이_같은_값이다():
    # ③ 10~1 (거꾸로) → 정렬하면 ①과 같으므로 9.55
    assert p95(list(range(10, 0, -1))) == pytest.approx(9.55)


def test_값이_2개면_둘_사이를_보간한다():
    # ④ [10, 20]
    #    위치 = (2 - 1) × 0.95 = 0.95 → 10 + 0.95 × (20 - 10) = 19.5
    assert p95([10, 20]) == pytest.approx(19.5)


def test_값이_1개면_그_값이다():
    # ⑤ [12.5] — statistics.quantiles는 값이 2개 미만이면 에러를 내므로 따로 처리한 경로
    assert p95([12.5]) == pytest.approx(12.5)


def test_값이_없으면_0이다():
    # ⑥ [] → 0.0 (기존 회차 파일 evals/runs/*.json과 같은 약속)
    assert p95([]) == 0.0
