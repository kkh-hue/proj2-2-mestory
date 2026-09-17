"""
데이터 창고 담당: CSV 파일을 읽어서 표(DataFrame)로 돌려주는 함수 모음

왜 따로 파일을 만들었나?
  - 창구(조회 함수)들은 "어디서 데이터를 가져오는지" 몰라도 되게 하려고.
  - 나중에 CSV 대신 Postgres(DB)를 쓰게 되면 이 파일만 고치면 된다.
    조회 함수들은 그대로 둬도 된다.
"""

import os
from pathlib import Path

import pandas as pd

# ─────────────────────────────────────────────
# 1. 데이터 폴더 위치
# ─────────────────────────────────────────────
# 이 파일 위치: proj2-2/mcp_server/tools/data_loader.py
#   .parent        → proj2-2/mcp_server/tools
#   .parents[2]    → proj2-2 (저장소 맨 위 폴더)
REPO_ROOT = Path(__file__).resolve().parents[2]

# 기본 데이터 폴더: proj2-2/data
# 단, 환경변수 MESTORY_DATA_DIR 가 있으면 그 경로를 우선 사용한다.
#   → Docker나 다른 컴퓨터에서 데이터 위치가 달라도 코드를 고치지 않아도 된다.
# os.getenv("이름", 기본값) = 환경변수가 있으면 그 값, 없으면 기본값
DATA_DIR = Path(os.getenv("MESTORY_DATA_DIR", REPO_ROOT / "data"))

# 파일 이름을 한곳에 모아 둔다. 이름이 바뀌면 여기만 고치면 된다.
DOWNTIME_FILE = "downtime_log.csv"
ERROR_CODE_FILE = "error_code_dict.csv"
MAINTENANCE_FILE = "maintenance_history.csv"
EQUIPMENT_FILE = "equipment_master.csv"


# ─────────────────────────────────────────────
# 2. CSV 하나를 읽는 공통 함수
# ─────────────────────────────────────────────
def _read_csv(file_name: str) -> pd.DataFrame:
    """데이터 폴더에서 CSV 하나를 읽는다.

    함수 이름 앞의 _ 는 "이 파일 안에서만 쓰는 함수"라는 관례 표시다.
    """
    path = DATA_DIR / file_name

    # 파일이 없으면 알아보기 쉬운 에러를 낸다.
    # (그냥 두면 pandas가 긴 영어 에러를 내서 원인 찾기가 어렵다)
    if not path.exists():
        raise FileNotFoundError(
            f"데이터 파일이 없습니다: {path}\n"
            f"proj2-2/data 폴더에 CSV를 넣거나, 환경변수 MESTORY_DATA_DIR로 위치를 지정하세요."
        )

    # utf-8-sig      : 파일 맨 앞의 BOM 표시를 떼서 첫 컬럼 이름이 깨지지 않게 함
    # keep_default_na: 빈 칸을 NaN으로 바꾸지 않고 빈 글자("")로 남김
    return pd.read_csv(path, encoding="utf-8-sig", keep_default_na=False)


# ─────────────────────────────────────────────
# 3. 파일별로 읽는 함수 (창구들은 이 함수들만 부른다)
# ─────────────────────────────────────────────
def load_downtime_logs() -> pd.DataFrame:
    """정지 로그를 읽고, 시작 시각을 날짜 형식으로 바꿔서 돌려준다."""
    df = _read_csv(DOWNTIME_FILE)

    # start_time은 "2026-01-01 20:39" 같은 글자로 저장돼 있다.
    # 날짜 비교(예: 8월 10일 기록만)를 하려면 진짜 날짜 형식으로 바꿔야 한다.
    # 원본 글자는 그대로 두고, 계산용 컬럼 _start_dt 를 새로 만든다.
    df["_start_dt"] = pd.to_datetime(df["start_time"])
    return df


def load_error_codes() -> pd.DataFrame:
    """에러코드 사전을 읽는다."""
    return _read_csv(ERROR_CODE_FILE)


def load_maintenance() -> pd.DataFrame:
    """정비 이력을 읽는다."""
    return _read_csv(MAINTENANCE_FILE)


def load_equipment() -> pd.DataFrame:
    """설비 목록을 읽는다."""
    return _read_csv(EQUIPMENT_FILE)
