"""
데이터 창고(data_loader) 시험 — CSV 모드와 DB 모드가 같은 결과를 내는지 확인한다.

monkeypatch 란?
  시험 하나가 도는 동안에만 환경변수를 잠깐 바꿔 주는 pytest 도구.
  시험이 끝나면 원래 값으로 자동으로 되돌린다. (다른 시험에 영향 없음)
"""

import os

import pandas as pd
import pytest

from mcp_server.tools import data_loader
from mcp_server.tools.data_loader import (
    DATA_DIR, DOWNTIME_FILE, EQUIPMENT_FILE, ERROR_CODE_FILE, MAINTENANCE_FILE,
)

# 읽기 함수와 "기록 번호" 컬럼 짝 (비교할 때 이 번호로 줄을 맞춘다)
LOADERS = [
    (data_loader.load_downtime_logs, "log_id"),
    (data_loader.load_error_codes, "error_code"),
    (data_loader.load_maintenance, "maintenance_id"),
    (data_loader.load_equipment, "equipment_id"),
]


@pytest.mark.no_data
def test_스위치_값이_잘못되면_에러(monkeypatch):
    """MESTORY_DATA_SOURCE 에 csv/db 말고 다른 값이 오면 설정 에러"""
    monkeypatch.setenv("MESTORY_DATA_SOURCE", "excel")
    with pytest.raises(RuntimeError):
        data_loader.load_error_codes()


@pytest.mark.no_data
def test_DB_모드인데_주소가_없으면_에러(monkeypatch):
    """DB 모드인데 접속 주소가 없으면 알아보기 쉬운 설정 에러"""
    monkeypatch.setenv("MESTORY_DATA_SOURCE", "db")
    monkeypatch.delenv("DATABASE_URL", raising=False)        # raising=False: 원래 없어도 괜찮음
    monkeypatch.delenv("DATABASE_PUBLIC_URL", raising=False)
    with pytest.raises(RuntimeError, match="DB 접속 주소"):
        data_loader.load_error_codes()


@pytest.mark.no_data
@pytest.mark.parametrize("loader, key", LOADERS, ids=["downtime", "error_codes", "maintenance", "equipment"])
def test_CSV와_DB가_같은_표를_돌려준다(monkeypatch, loader, key):
    """CSV 와 DB 둘 다 있을 때만 실행: 내용·컬럼·자료형이 모두 같아야 한다"""
    csv_ready = all((DATA_DIR / f).exists()
                    for f in (DOWNTIME_FILE, ERROR_CODE_FILE, MAINTENANCE_FILE, EQUIPMENT_FILE))
    db_ready = bool(os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL"))
    if not (csv_ready and db_ready):
        pytest.skip("CSV 와 DB 접속 주소가 둘 다 있어야 비교할 수 있습니다")

    monkeypatch.setenv("MESTORY_DATA_SOURCE", "csv")
    from_csv = loader()
    monkeypatch.setenv("MESTORY_DATA_SOURCE", "db")
    from_db = loader()

    # 에러코드 사전은 CSV 저장 순서가 번호순이 아니라서, 둘 다 번호순으로 줄을 맞춘 뒤 비교한다
    # reset_index(drop=True) = 정렬 후 줄 번호를 0, 1, 2 ... 로 다시 매기기
    from_csv = from_csv.sort_values(key).reset_index(drop=True)
    from_db = from_db.sort_values(key).reset_index(drop=True)

    # assert_frame_equal = 두 표가 값·컬럼 이름·자료형까지 같은지 확인 (다르면 어디가 다른지 알려 줌)
    pd.testing.assert_frame_equal(from_csv, from_db)
