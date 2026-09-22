-- 실행하지 않는 준비용 migration. 기존 seed_db.py와 DB에는 영향을 주지 않는다.
create table if not exists users (
    user_id uuid primary key,
    email text not null unique,
    password_hash text not null,
    created_at timestamptz not null default now()
);

create table if not exists analysis_history (
    history_id uuid primary key,
    user_id uuid not null references users(user_id) on delete cascade,
    analyzed_at timestamptz not null default now(),
    date_from date,
    date_to date,
    line_id text,
    equipment_id text,
    report_json jsonb not null
);

create index if not exists idx_analysis_history_user_analyzed_at
    on analysis_history (user_id, analyzed_at desc);
