"""
pytest 공통 준비 파일.

conftest.py 란?
  pytest 가 시험 파일들보다 "먼저" 읽는 준비 파일이다.
  여기 적은 설정은 tests/ 폴더 안의 모든 시험에 똑같이 적용된다.

여기서 하는 일
  1. 저장소 맨 위 폴더(proj2-2)를 불러오기 경로에 넣는다.
     → 어느 폴더에서 pytest 를 실행해도 `from mcp_server...` 가 동작하게.
  2. CSV 데이터(data/)가 없으면 시험을 "건너뜀(skip)"으로 처리한다.
     → data/ 는 .gitignore 라 GitHub 에 없다. 데이터가 없는 PC 에서
       "실패"로 보이지 않게, 이유를 적고 건너뛴다.
"""

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
MISSING = [name for name in (DOWNTIME_FILE, ERROR_CODE_FILE, MAINTENANCE_FILE, EQUIPMENT_FILE)
           if not (DATA_DIR / name).exists()]


def pytest_collection_modifyitems(config, items):
    """pytest 가 시험 목록을 다 모은 뒤 부르는 함수. 데이터가 없으면 전부 skip 표시를 붙인다."""
    if not MISSING:
        return  # 데이터가 다 있으면 아무것도 안 함
    skip = pytest.mark.skip(reason=f"CSV 데이터가 없습니다 ({DATA_DIR}): {', '.join(MISSING)}")
    for item in items:
        item.add_marker(skip)
