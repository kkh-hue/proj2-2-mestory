"""
MCP 서버 — 필수 조건 5.

한 줄 요약
  "창구 3개(tools/*.py)에 이름표를 붙여서, AI가 골라 부를 수 있게 등록하는 곳"

누가 이 서버를 띄우나
  - 백엔드(backend/services/llm.py)가 `python -m mcp_server.server` 명령으로
    이 서버를 자식 프로세스로 띄우고, stdio(표준 입출력) 통로로 대화한다.
  - 그래서 이 파일은 stdio 방식(mcp.run() 기본값)으로 실행한다.
  - 주의: stdio 방식에서는 print()로 화면에 글을 찍으면 대화 통로가 깨진다.
          여기와 tools/ 안에서는 print()를 쓰지 않는다.

도구 3개
  1. get_downtime_logs        : 정지 로그 조회 + 사실 요약 + 주의 딱지   (tools/downtime.py)
  2. get_error_code_info      : 에러코드 사전 조회                        (tools/error_codes.py)
  3. get_maintenance_history  : 설비의 최근 정비 이력 조회                (tools/maintenance.py)

설계 원칙
  - 실제 조회 로직은 tools/ 에만 둔다. 여기서는 "이름표(설명문)"와 "에러 처리"만 한다.
  - AI는 함수 이름과 설명문(docstring)만 보고 어떤 도구를 쓸지 고른다.
    → 설명문에 "언제 쓰는지 / 무엇을 넣는지 / 결과를 어떻게 다뤄야 하는지"를 적는다.
  - 입력이 잘못돼도 서버가 멈추지 않게, 에러를 {"error": "..."} 모양으로 돌려준다.
    → AI가 메시지를 읽고 입력을 고쳐서 다시 부를 수 있다.
"""

# `python -m mcp_server.server` 로 실행되므로, 저장소 맨 위 폴더 기준으로 불러온다
from mcp.server.fastmcp import FastMCP

from mcp_server.tools.downtime import query_downtime_logs
from mcp_server.tools.error_codes import lookup_error_codes
from mcp_server.tools.maintenance import query_maintenance_history

# 서버 이름: MCP 클라이언트(백엔드, Claude Desktop 등) 화면에 보이는 이름
mcp = FastMCP("mestory-downtime")

# AI 에게 돌려줄 정지 기록 기본 개수.
# 기록 한 줄이 꽤 길어서, 많이 보내면 비용이 커진다. 요약(summary)은 개수와 상관없이 전체 기준이다.
TOOL_DEFAULT_LIMIT = 50


def _error(message: str, hint: str = "입력값을 고쳐서 다시 호출하세요.") -> dict:
    """에러를 AI 가 읽을 수 있는 모양으로 만든다."""
    return {"error": message, "hint": hint}


# ─────────────────────────────────────────────
# 도구 1. 정지 로그 조회
# ─────────────────────────────────────────────
@mcp.tool()
def get_downtime_logs(
    date_from: str | None = None,
    date_to: str | None = None,
    line_id: str | None = None,
    equipment_id: str | None = None,
    error_code: str | None = None,
    min_downtime: float | None = None,
    max_downtime: float | None = None,
    limit: int = TOOL_DEFAULT_LIMIT,
) -> dict:
    """설비 정지(다운타임) 기록을 조건으로 조회하고, 사실 요약과 주의 표시를 함께 돌려준다.
    원인 분석 리포트를 만들 때 가장 먼저 호출한다.

    Args:
        date_from: 조회 시작일 YYYY-MM-DD (정지 시작일 기준, 이 날 포함)
        date_to: 조회 종료일 YYYY-MM-DD (이 날 포함)
        line_id: 라인 ID. 예: LINE-A
        equipment_id: 설비 ID. 예: EQ-001
        error_code: 특정 에러코드만 볼 때. 예: E-102
        min_downtime: 정지시간 최소(분)
        max_downtime: 정지시간 최대(분)
        limit: 돌려받을 기록 수 (기본 50, 최대 1000)

    결과 읽는 법:
        - summary 는 조건에 맞는 "전체" 기록 기준이다. 건수·총 정지시간·코드별 순위는 summary 값을 그대로 쓴다.
        - summary.by_error_code 는 계획 정지와 판정 불가 기록을 뺀 "조치가 필요한 원인 후보"다.
        - flags 가 붙은 기록(summary.needs_check)은 원인을 추정하지 말고 '확인 필요'로 보고한다.
        - truncated 가 true 면 rows 는 일부만 온 것이다.
        - warnings 에 없는 ID 경고가 있으면 결과 0건을 "정지 없음"으로 해석하지 않는다.
    """
    try:
        return query_downtime_logs(
            date_from=date_from, date_to=date_to, line_id=line_id,
            equipment_id=equipment_id, error_code=error_code,
            min_downtime=min_downtime, max_downtime=max_downtime, limit=limit,
        )
    except ValueError as e:        # 날짜 형식 오류 등 "입력" 문제
        return _error(str(e))
    except (RuntimeError, FileNotFoundError) as e:   # 데이터·설정 문제 (CSV 없음, 스위치 오류)
        return _error(str(e), hint="데이터 설정 문제입니다. 입력값을 바꿔도 해결되지 않습니다.")


# ─────────────────────────────────────────────
# 도구 2. 에러코드 사전 조회
# ─────────────────────────────────────────────
@mcp.tool()
def get_error_code_info(error_codes: list[str]) -> dict:
    """에러코드의 뜻·분류·흔한 원인·보통 정지시간·기본 심각도를 사전에서 조회한다.
    정지 기록에 나온 에러코드를 해석할 때 호출하며, 여러 코드를 한 번에 넣는다.

    Args:
        error_codes: 조회할 에러코드 목록. 예: ["E-102", "M-204"]

    결과 읽는 법:
        - found 가 false 인 코드는 사전에 없는 코드다. 원인을 절대 추정하지 말고 '판정 불가 — 현장 확인 필요'로 보고한다.
        - typical_min / typical_max 는 보통 정지시간(분)이다. 실제 정지시간과 비교할 때 쓴다.
        - severity_hint 는 참고용 기본 심각도다.
        - is_planned_stop 이 true 면 고장이 아닌 계획 정지다. 조치가 필요한 원인으로 보고하지 않는다.
        - is_unknown_cause 가 true 면 '원인 미확인' 코드다. 원인을 추정하지 않는다.
    """
    try:
        return lookup_error_codes(error_codes)
    except ValueError as e:
        return _error(str(e))
    except (RuntimeError, FileNotFoundError) as e:   # 데이터·설정 문제 (CSV 없음, 스위치 오류)
        return _error(str(e), hint="데이터 설정 문제입니다. 입력값을 바꿔도 해결되지 않습니다.")


# ─────────────────────────────────────────────
# 도구 3. 정비이력 조회
# ─────────────────────────────────────────────
@mcp.tool()
def get_maintenance_history(
    equipment_id: str,
    reference_date: str,
    days: int = 30,
) -> dict:
    """설비 하나의 최근 정비 기록(예방/사후, 조치 내용, 결과)을 조회한다.
    같은 고장이 반복되는지, 최근에 수리했는지 근거가 필요할 때 호출한다.

    Args:
        equipment_id: 설비 ID. 예: EQ-001
        reference_date: 리포트 기준 날짜 YYYY-MM-DD. 보통 조회 기간의 마지막 날(date_to)을 넣는다.
        days: 기준 날짜로부터 며칠 전까지 볼지 (기본 30, 최대 365)

    결과 읽는 법:
        - RECURRENCE_RISK 표시는 '임시 조치, 재발 가능성 있음' 기록이다. 이번 정지가 재발일 가능성을 근거로 제시하되 단정하지 않는다.
        - PENDING_REWORK 표시는 수리가 아직 끝나지 않은 기록이다.
        - summary.note 에 '정비 기록이 없습니다'가 있으면 정기 점검이 필요할 수 있다고 언급한다.
    """
    try:
        return query_maintenance_history(
            equipment_id=equipment_id, reference_date=reference_date, days=days,
        )
    except ValueError as e:
        return _error(str(e))
    except (RuntimeError, FileNotFoundError) as e:   # 데이터·설정 문제 (CSV 없음, 스위치 오류)
        return _error(str(e), hint="데이터 설정 문제입니다. 입력값을 바꿔도 해결되지 않습니다.")


# 이 파일을 직접 실행했을 때만 서버를 켠다 (stdio 방식)
if __name__ == "__main__":
    mcp.run()
