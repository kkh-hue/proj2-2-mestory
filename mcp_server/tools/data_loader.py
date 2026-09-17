"""
데이터 창고 담당: CSV 파일 또는 Postgres(DB)에서 표(DataFrame)를 읽어서 돌려주는 함수 모음

왜 따로 파일을 만들었나?
  - 창구(조회 함수)들은 "어디서 데이터를 가져오는지" 몰라도 되게 하려고.
  - CSV 에서 읽든 DB 에서 읽든, 이 파일이 **똑같은 모양의 표**를 돌려준다.
    그래서 조회 함수들(downtime.py 등)은 고치지 않아도 된다.

어디서 읽을지 정하는 스위치 (환경변수)
  MESTORY_DATA_SOURCE = csv (기본값) → proj2-2/data 의 CSV 를 읽는다
  MESTORY_DATA_SOURCE = db           → Postgres 를 읽는다
                                        (접속 주소: DATABASE_URL 또는 DATABASE_PUBLIC_URL)

  왜 "주소가 있으면 자동으로 DB" 로 하지 않았나?
    docker-compose 에는 비어 있는 Postgres(db) 도 있어서, 주소만 보고 붙으면
    빈 DB 를 읽어 조회 결과가 0건이 될 수 있다. 스위치를 따로 두면 실수가 없다.
"""

import os
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────
# 1. CSV 폴더 위치 (CSV 모드에서 사용)
# ─────────────────────────────────────────────
# 이 파일 위치: proj2-2/mcp_server/tools/data_loader.py
#   .parents[2] → proj2-2 (저장소 맨 위 폴더)
REPO_ROOT = Path(__file__).resolve().parents[2]

# 기본 데이터 폴더: proj2-2/data
# 환경변수 MESTORY_DATA_DIR 가 있으면 그 경로를 우선 사용한다.
DATA_DIR = Path(os.getenv("MESTORY_DATA_DIR", REPO_ROOT / "data"))

# 파일 이름을 한곳에 모아 둔다. 이름이 바뀌면 여기만 고치면 된다.
DOWNTIME_FILE = "downtime_log.csv"
ERROR_CODE_FILE = "error_code_dict.csv"
MAINTENANCE_FILE = "maintenance_history.csv"
EQUIPMENT_FILE = "equipment_master.csv"


# ─────────────────────────────────────────────
# 2. DB 에서 읽을 때 쓰는 SQL (DB 모드에서 사용)
# ─────────────────────────────────────────────
# 목표: CSV 로 읽었을 때와 "글자 하나까지" 같은 표를 만든다.
#   - coalesce(칸, '')          : 값이 없으면(NULL) 빈 글자로 → CSV 의 빈 칸과 같게
#   - to_char(시각, '형식')      : 날짜·시각을 CSV 와 같은 글자 모양으로
#   - downtime_min::float8      : 숫자를 파이썬 소수(float)로 → CSV 와 같은 자료형
#   - order by ... collate "C"  : 기록 번호 순서로 정렬 (CSV 도 번호 순서로 저장돼 있음)
#                                 collate "C" = 컴퓨터 언어 설정과 상관없이 글자 코드 순서로
# 테이블 구조는 scripts/seed_db.py 에서 만든 것과 같다.
SQL = {
    DOWNTIME_FILE: """
        select log_id,
               coalesce(line_id, '')                                   as line_id,
               coalesce(equipment_id, '')                              as equipment_id,
               coalesce(to_char(start_time, 'YYYY-MM-DD HH24:MI'), '') as start_time,
               coalesce(to_char(end_time,   'YYYY-MM-DD HH24:MI'), '') as end_time,
               downtime_min::float8                                    as downtime_min,
               coalesce(error_code, '')                                as error_code,
               coalesce(shift, '')                                     as shift,
               coalesce(operator_note, '')                             as operator_note
        from downtime_log
        order by log_id collate "C"
    """,
    ERROR_CODE_FILE: """
        select error_code,
               coalesce(category, '')                   as category,
               coalesce(description, '')                as description,
               coalesce(typical_cause, '')              as typical_cause,
               coalesce(typical_duration_min_range, '') as typical_duration_min_range,
               coalesce(severity_hint, '')              as severity_hint
        from error_code_dict
        order by error_code collate "C"
    """,
    MAINTENANCE_FILE: """
        select maintenance_id,
               coalesce(equipment_id, '')                  as equipment_id,
               coalesce(to_char("date", 'YYYY-MM-DD'), '') as "date",
               coalesce(type, '')                          as type,
               coalesce(action_taken, '')                  as action_taken,
               coalesce(result, '')                        as result
        from maintenance_history
        order by maintenance_id collate "C"
    """,
    EQUIPMENT_FILE: """
        select equipment_id,
               coalesce(line_id, '')                             as line_id,
               coalesce(equipment_type, '')                      as equipment_type,
               coalesce(to_char(install_date, 'YYYY-MM-DD'), '') as install_date,
               coalesce(spec_threshold, '')                      as spec_threshold
        from equipment_master
        order by equipment_id collate "C"
    """,
}


# ─────────────────────────────────────────────
# 3. 스위치 읽기
# ─────────────────────────────────────────────
def get_data_source() -> str:
    """지금 어디서 읽는지("csv" 또는 "db")를 돌려준다.

    함수 안에서 매번 읽는 이유: 시험(pytest)에서 환경변수를 바꿔 가며 확인할 수 있게.
    """
    source = os.getenv("MESTORY_DATA_SOURCE", "csv").strip().lower()
    if source not in ("csv", "db"):
        # 사용자 입력 문제가 아니라 "설정" 문제라서 ValueError 대신 RuntimeError 를 쓴다
        # (server.py 는 ValueError 만 '입력값을 고치라'는 안내로 바꾸기 때문)
        raise RuntimeError(
            f"MESTORY_DATA_SOURCE 값이 잘못됐습니다: '{source}' (csv 또는 db 만 가능)"
        )
    return source


# ─────────────────────────────────────────────
# 4. CSV 하나를 읽는 함수
# ─────────────────────────────────────────────
def _read_csv(file_name: str) -> pd.DataFrame:
    """데이터 폴더에서 CSV 하나를 읽는다."""
    path = DATA_DIR / file_name

    # 파일이 없으면 알아보기 쉬운 에러를 낸다
    if not path.exists():
        raise FileNotFoundError(
            f"데이터 파일이 없습니다: {path}\n"
            f"proj2-2/data 폴더에 CSV를 넣거나, 환경변수 MESTORY_DATA_DIR로 위치를 지정하세요.\n"
            f"(DB 에서 읽으려면 MESTORY_DATA_SOURCE=db 로 설정)"
        )

    # utf-8-sig      : 파일 맨 앞의 BOM 표시를 떼서 첫 컬럼 이름이 깨지지 않게 함
    # keep_default_na: 빈 칸을 NaN으로 바꾸지 않고 빈 글자("")로 남김
    return pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)


# ─────────────────────────────────────────────
# 5. DB 에서 테이블 하나를 읽는 함수
# ─────────────────────────────────────────────
def _get_database_url() -> str:
    """DB 접속 주소를 환경변수에서 찾는다 (scripts/seed_db.py 와 같은 규칙)."""
    url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
    if not url:
        raise RuntimeError(
            "MESTORY_DATA_SOURCE=db 인데 DB 접속 주소가 없습니다. "
            "환경변수 DATABASE_URL(또는 DATABASE_PUBLIC_URL)을 설정하세요."
        )
    return url


def _read_db(file_name: str) -> pd.DataFrame:
    """DB 에서 CSV 파일 하나에 해당하는 테이블을 읽어, CSV 와 같은 모양의 표로 돌려준다."""
    # psycopg(Postgres 접속 도구)는 DB 모드일 때만 필요하다.
    # 함수 안에서 불러오면, CSV 모드에서는 psycopg 가 설치돼 있지 않아도 동작한다.
    import psycopg

    # connect_timeout=10 : DB 가 응답하지 않으면 10초 뒤 포기 (무한 대기 방지)
    # with 블록이 끝나면 접속이 자동으로 닫힌다
    with psycopg.connect(_get_database_url(), connect_timeout=10) as conn:
        cur = conn.execute(SQL[file_name])                # SQL 보내기
        rows = cur.fetchall()                             # 결과 행 전부 받기
        columns = [col.name for col in cur.description]   # 컬럼 이름 목록

    df = pd.DataFrame(rows, columns=columns)

    # 행이 0개면 pandas 가 숫자 칸의 자료형을 모르므로, CSV 와 같게 소수형으로 맞춘다
    if "downtime_min" in df.columns:
        df["downtime_min"] = df["downtime_min"].astype(float)
    return df


# ─────────────────────────────────────────────
# 6. 스위치에 따라 CSV 또는 DB 에서 읽기
# ─────────────────────────────────────────────
def _read_table(file_name: str) -> pd.DataFrame:
    if get_data_source() == "db":
        return _read_db(file_name)
    return _read_csv(file_name)


# ─────────────────────────────────────────────
# 7. 표별로 읽는 함수 (창구들은 이 함수들만 부른다 — 이름·결과 모양은 예전과 같음)
# ─────────────────────────────────────────────
def load_downtime_logs() -> pd.DataFrame:
    """정지 로그를 읽고, 시작 시각을 날짜 형식으로 바꿔서 돌려준다."""
    df = _read_table(DOWNTIME_FILE)

    # start_time 은 "2026-01-01 20:39" 같은 글자다.
    # 날짜 비교를 하려고 계산용 컬럼 _start_dt 를 새로 만든다 (원본 글자는 그대로 둠).
    df["_start_dt"] = pd.to_datetime(df["start_time"])
    return df


def load_error_codes() -> pd.DataFrame:
    """에러코드 사전을 읽는다."""
    return _read_table(ERROR_CODE_FILE)


def load_maintenance() -> pd.DataFrame:
    """정비 이력을 읽는다."""
    return _read_table(MAINTENANCE_FILE)


def load_equipment() -> pd.DataFrame:
    """설비 목록을 읽는다."""
    return _read_table(EQUIPMENT_FILE)
