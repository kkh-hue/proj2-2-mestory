"""지연 시간(초) 목록에서 p95를 구한다 — scripts/score_multimodal.py가 쓴다.

왜 따로 파일을 두나
  score_multimodal.py는 import되는 순간 .env를 읽는다(load_dotenv). 테스트가 그 파일을
  불러오면 .env의 DATABASE_URL 등이 pytest 전체에 섞여 다른 테스트가 깨진다.
  이 파일은 표준 라이브러리만 써서 불러와도 부작용이 없다.

옛 계산이 틀렸던 이유
  s[min(len(s) - 1, int(len(s) * 0.95))] — 정렬한 값 중 "가장 가까운 순위" 하나를 고르는 방식인데,
  10건이면 int(9.5) = 9 → 정렬한 10개의 마지막 = 최댓값이었다.
  30건이어도 int(28.5) = 28 → 뒤에서 두 번째. 건수를 늘려도 p95가 되지 않았다.
"""

from __future__ import annotations

import statistics


def p95(latencies: list[float]) -> float:
    """정렬한 값 사이를 선형보간한 95번째 백분위를 소수 둘째 자리까지 돌려준다.

    위치 = (건수 - 1) × 0.95 (0부터 센 순번).
      예) 10건 → 8.55번째 = 정렬한 값의 8번째와 9번째 사이에서 9번째 쪽으로 55% 지점
    """
    # 1단계: 값이 없으면 0.0 — 기존 회차 파일(evals/runs/*.json)과 같은 약속
    if not latencies:
        return 0.0

    # 2단계: 값이 1개면 그 값이 곧 p95
    #        (statistics.quantiles는 값이 2개 미만이면 StatisticsError를 낸다)
    if len(latencies) == 1:
        return round(float(latencies[0]), 2)

    # 3단계: statistics.quantiles를 쓰는 이유 — 표준 라이브러리이고, method="inclusive"가
    #        최솟값을 0번째·최댓값을 100번째 백분위로 보고 그 사이를 선형보간한다(numpy 기본값과 같은 방식).
    #        n=100이면 1~99번째 백분위 경계 99개가 나오고, 95번째는 [94]다.
    cut_points = statistics.quantiles(latencies, n=100, method="inclusive")
    return round(cut_points[94], 2)
