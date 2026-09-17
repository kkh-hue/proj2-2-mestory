"""
DB 적재 스크립트: 시뮬레이션 CSV 4개를 Postgres 테이블 4개에 넣는다.

한 줄 요약
  "창고(CSV 파일)에 있는 재료를 새 창고(Postgres DB)로 옮겨 담는 이삿짐 직원"

어디서 실행하나
  - Railway에 배포해서 실행하면, Railway가 넣어 주는 환경변수 DATABASE_URL 로 DB에 접속한다.
  - 내 PC에서 시험할 때는 .env 나 터미널에 DATABASE_URL 을 직접 넣고 실행한다.

실행 방법 (proj2-2 폴더에서)
  python scripts/seed_db.py            # 테이블이 없으면 만들고, 데이터를 새로 채움
  python scripts/seed_db.py --reset    # 테이블을 지우고 처음부터 다시 만듦 (컬럼 구조가 바뀌었을 때)

여러 번 실행해도 괜찮나?
  - 괜찮다. 넣기 전에 테이블 안의 기존 데이터를 비우고(TRUNCATE) 다시 넣기 때문에
    두 번 실행해도 데이터가 두 배로 쌓이지 않는다.
  - 비우기와 넣기를 "한 묶음(트랜잭션)"으로 처리해서, 중간에 실패하면 전부 없던 일이 된다.
"""

# ─────────────────────────────────────────────
# 1단계. 필요한 도구 불러오기
# ─────────────────────────────────────────────
import argparse   # 실행할 때 --reset 같은 옵션을 받기 위한 도구
import os         # 환경변수(DATABASE_URL)를 읽기 위한 도구
import sys
from pathlib import Path

import pandas as pd
import psycopg    # 파이썬에서 Postgres 에 접속하는 라이브러리 (pip install "psycopg[binary]")

# 이 파일 위치: proj2-2/scripts/seed_db.py → 한 칸 위(proj2-2)를 불러오기 경로에 추가
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# CSV 읽기는 창구들이 쓰는 창고 담당(data_loader)과 똑같은 방법을 쓴다.
# → CSV 로 읽을 때와 DB 로 읽을 때 값이 똑같이 들어가게 하기 위해서
from mcp_server.tools.data_loader import (  # noqa: E402
    DATA_DIR, DOWNTIME_FILE, EQUIPMENT_FILE, ERROR_CODE_FILE, MAINTENANCE_FILE, _read_csv,
)


# ─────────────────────────────────────────────
# 2단계. 테이블 설계도 (CSV 파일 하나 = 테이블 하나)
# ─────────────────────────────────────────────
# 외래 키(다른 테이블에 꼭 있어야 한다는 규칙)는 일부러 걸지 않는다.
#   → EQ-058(없는 설비), X-999(없는 코드) 같은 함정 데이터도 그대로 넣어야
#     창구가 그걸 찾아서 "주의 딱지"를 붙일 수 있기 때문이다.
TABLES = {
    "error_code_dict": {
        "csv": ERROR_CODE_FILE,
        "ddl": """
            create table if not exists error_code_dict (
                error_code                 text primary key,  -- 코드 (겹치면 안 됨)
                category                   text,              -- 분류 (전기, 기계 ...)
                description                text,              -- 코드 뜻
                typical_cause              text,              -- 흔한 원인
                typical_duration_min_range text,              -- 보통 정지시간 "10~30"
                severity_hint              text               -- 기본 심각도
            )""",
    },
    "equipment_master": {
        "csv": EQUIPMENT_FILE,
        "ddl": """
            create table if not exists equipment_master (
                equipment_id   text primary key,  -- 설비 번호
                line_id        text,              -- 설비가 있는 라인
                equipment_type text,              -- 설비 종류
                install_date   date,              -- 설치일
                spec_threshold text               -- 정상 가동 범위
            )""",
    },
    "maintenance_history": {
        "csv": MAINTENANCE_FILE,
        "ddl": """
            create table if not exists maintenance_history (
                maintenance_id text primary key,  -- 정비 기록 번호
                equipment_id   text,
                "date"         date,              -- date 는 SQL 예약어라 따옴표로 감쌈
                type           text,              -- 예방 / 사후
                action_taken   text,
                result         text
            )""",
    },
    "downtime_log": {
        "csv": DOWNTIME_FILE,
        "ddl": """
            create table if not exists downtime_log (
                log_id        text primary key,   -- 기록 번호
                line_id       text,
                equipment_id  text,
                start_time    timestamp,          -- 멈춘 시각
                end_time      timestamp,          -- 다시 돈 시각
                downtime_min  numeric,            -- 정지시간(분). 음수 함정 데이터도 그대로
                error_code    text,               -- 빈 값·없는 코드도 그대로
                shift         text,
                operator_note text
            )""",
    },
}

# 자주 찾는 칸에 "찾아보기 목차(색인)"를 만들어 조회를 빠르게 한다
INDEXES = [
    "create index if not exists idx_downtime_start on downtime_log (start_time)",
    "create index if not exists idx_downtime_equipment on downtime_log (equipment_id)",
    'create index if not exists idx_maint_equipment on maintenance_history (equipment_id, "date")',
]


# ─────────────────────────────────────────────
# 3단계. 접속 주소 가져오기
# ─────────────────────────────────────────────
def get_database_url() -> str:
    """환경변수에서 DB 접속 주소를 찾는다.

    - DATABASE_URL        : Railway 안에서 쓰는 내부 주소 (Railway에 배포해서 실행할 때)
    - DATABASE_PUBLIC_URL : 밖에서 쓰는 공개 주소 (내 PC에서 시험할 때, 공개 접속을 켠 경우만 있음)
    """
    url = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
    if not url:
        # 비밀번호가 들어 있는 주소라서, 코드에 직접 적지 않고 환경변수로만 받는다
        raise SystemExit(
            "DB 접속 주소가 없습니다. 환경변수 DATABASE_URL 을 설정하세요.\n"
            "(Railway 서비스의 Variables 탭에서 Postgres 의 DATABASE_URL 을 연결)"
        )

    # Railway 화면에서 "${{PGUSER}}" 같은 빈칸 틀을 그대로 복사해 오는 실수 막기
    # (진짜 주소에는 "${{" 가 들어 있지 않다)
    if "${{" in url:
        raise SystemExit(
            "접속 주소가 아직 '틀' 모양입니다 (${{...}} 가 들어 있음).\n"
            "Railway Postgres 에서 Public Networking(TCP Proxy)을 켠 뒤,\n"
            "Variables 탭의 DATABASE_PUBLIC_URL '실제 값'(눈 아이콘)을 복사해서 다시 넣으세요."
        )
    return url


# ─────────────────────────────────────────────
# 4단계. CSV 한 개를 DB 에 넣기
# ─────────────────────────────────────────────
def load_table(cur, table: str, csv_name: str) -> int:
    """CSV 를 읽어서 테이블에 넣고, 넣은 행 수를 돌려준다."""
    df = _read_csv(csv_name)   # 빈 칸은 빈 글자("")로 읽힘 (창구와 같은 방식)

    # 날짜 칸의 빈 글자는 날짜로 바꿀 수 없으니 None(값 없음)으로 바꾼다
    for col in ("install_date", "date", "start_time", "end_time"):
        if col in df.columns:
            # [A if 조건 else B for v in 목록] = 목록을 한 칸씩 보며 값을 바꾸는 짧은 문법
            df[col] = [None if v == "" else v for v in df[col]]

    # 기존 데이터 비우기 → 여러 번 실행해도 두 배로 쌓이지 않음
    cur.execute(f"truncate table {table}")

    # COPY = 여러 행을 한 번에 빠르게 넣는 Postgres 전용 방법
    columns = ", ".join(f'"{c}"' for c in df.columns)   # 컬럼 이름을 따옴표로 감싸기 (date 대비)
    with cur.copy(f"copy {table} ({columns}) from stdin") as copy:
        for row in df.itertuples(index=False):           # 표를 한 줄씩 꺼내서
            copy.write_row(row)                           # DB 로 보냄

    return len(df)


# ─────────────────────────────────────────────
# 5단계. 전체 실행 순서
# ─────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="MESTORY 시뮬레이션 CSV → Postgres 적재")
    parser.add_argument("--reset", action="store_true",
                        help="테이블을 지우고 다시 만든다 (컬럼 구조를 바꿨을 때만 사용)")
    args = parser.parse_args()

    print(f"CSV 폴더: {DATA_DIR}")
    url = get_database_url()

    # with 블록이 끝나면 접속이 자동으로 닫힌다.
    # 블록 안에서 에러가 나면 지금까지 한 일이 모두 취소(rollback)된다.
    with psycopg.connect(url) as conn:
        with conn.cursor() as cur:   # cursor = DB 에 SQL 을 보내는 창구

            if args.reset:
                print("기존 테이블 삭제 (--reset)")
                for table in TABLES:
                    cur.execute(f"drop table if exists {table}")

            # 테이블과 색인 만들기 (이미 있으면 건너뜀)
            for table, spec in TABLES.items():
                cur.execute(spec["ddl"])
            for sql in INDEXES:
                cur.execute(sql)

            # 테이블마다 CSV 넣기
            for table, spec in TABLES.items():
                count = load_table(cur, table, spec["csv"])
                print(f"  {table:<20} {count:>6}행 넣음")

        # 여기까지 에러 없이 오면 conn 블록이 끝나면서 한꺼번에 저장(commit)된다

    # 제대로 들어갔는지 DB 에 다시 물어봐서 확인
    with psycopg.connect(url) as conn:
        print("\n적재 확인 (DB 에 실제로 들어 있는 행 수)")
        for table in TABLES:
            n = conn.execute(f"select count(*) from {table}").fetchone()[0]
            print(f"  {table:<20} {n:>6}행")

    print("\n완료")


# 이 파일을 직접 실행했을 때만 main() 을 돌린다 (다른 파일에서 import 할 때는 안 돌림)
if __name__ == "__main__":
    main()
