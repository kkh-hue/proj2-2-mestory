"""
pytest 공통 준비 파일.

conftest.py 란?
  pytest 가 시험 파일들보다 "먼저" 읽는 준비 파일이다.
  여기 적은 설정은 tests/ 폴더 안의 모든 시험에 똑같이 적용된다.

여기서 하는 일
  1. 저장소 맨 위 폴더(proj2-2)를 불러오기 경로에 넣는다.
     → 어느 폴더에서 pytest 를 실행해도 `from mcp_server...` 가 동작하게.
  2. 데이터가 없으면 시험을 "건너뜀(skip)"으로 처리한다.
     - CSV 모드(기본): data/ 폴더에 CSV 4개가 없으면 건너뜀
       (data/ 는 .gitignore 라 GitHub 에 없다)
     - DB 모드(MESTORY_DATA_SOURCE=db): DB 접속 주소가 없으면 건너뜀
     - @pytest.mark.no_data 가 붙은 시험은 데이터가 없어도 실행한다.
"""

import os
import sys
from pathlib import Path

import pytest

# 이 파일 위치: proj2-2/tests/conftest.py → 한 칸 위가 proj2-2
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from mcp_server.tools.data_loader import (  # noqa: E402  (경로를 넣은 뒤에 불러와야 해서 위치가 여기)
    DATA_DIR, DOWNTIME_FILE, EQUIPMENT_FILE, ERROR_CODE_FILE, MAINTENANCE_FILE,
)

# 시험에 필요한 CSV 4개 중 없는 파일 목록
CSV_MISSING = [name for name in (DOWNTIME_FILE, ERROR_CODE_FILE, MAINTENANCE_FILE, EQUIPMENT_FILE)
               if not (DATA_DIR / name).exists()]

# DB 접속 주소가 있는지 (값 자체는 쓰지 않고 "있다/없다"만 본다)
HAS_DB_URL = bool(os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL"))


def pytest_configure(config):
    """시험에 붙일 수 있는 표시(marker) 이름을 등록한다. 등록하지 않으면 pytest 가 경고를 낸다."""
    config.addinivalue_line("markers", "no_data: 데이터(CSV/DB) 없이도 실행하는 시험")


def _skip_reason() -> str | None:
    """지금 설정에서 데이터를 읽을 수 없으면 그 이유를, 읽을 수 있으면 None 을 돌려준다."""
    source = os.getenv("MESTORY_DATA_SOURCE", "csv").strip().lower()
    if source == "db":
        if not HAS_DB_URL:
            return "MESTORY_DATA_SOURCE=db 인데 DATABASE_URL(또는 DATABASE_PUBLIC_URL)이 없습니다"
        return None
    if CSV_MISSING:
        return f"CSV 데이터가 없습니다 ({DATA_DIR}): {', '.join(CSV_MISSING)}"
    return None


def pytest_collection_modifyitems(config, items):
    """pytest 가 시험 목록을 다 모은 뒤 부르는 함수. 데이터를 못 읽으면 skip 표시를 붙인다."""
    reason = _skip_reason()
    if reason is None:
        return  # 데이터를 읽을 수 있으면 아무것도 안 함

    skip = pytest.mark.skip(reason=reason)
    for item in items:
        # get_closest_marker("no_data") = 이 시험에 no_data 표시가 붙어 있으면 그 표시, 없으면 None
        if item.get_closest_marker("no_data") is None:
            item.add_marker(skip)
