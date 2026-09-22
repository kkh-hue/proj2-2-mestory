alter table chat_messages
    add column if not exists user_id bigint references users(id);

create index if not exists idx_chat_messages_user_session
    on chat_messages (user_id, session_id, created_at);
