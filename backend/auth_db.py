import os

import psycopg


class AuthDatabaseError(RuntimeError):
    """Authentication database operation failed."""


async def _connect() -> psycopg.AsyncConnection:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise AuthDatabaseError("DATABASE_URL is not configured.")

    return await psycopg.AsyncConnection.connect(database_url)


async def init_auth_db() -> None:
    """Create the users table if it does not exist."""
    try:
        async with await _connect() as conn:
            await conn.execute(
                """
                create table if not exists users (
                    id bigserial primary key,
                    email text not null unique,
                    password_hash text not null,
                    created_at timestamptz not null default now()
                )
                """
            )
    except Exception as exc:
        raise AuthDatabaseError(
            "Failed to initialize authentication database."
        ) from exc


async def get_user_by_email(email: str) -> dict | None:
    """Return one user by email."""
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                """
                select id, email, password_hash, created_at
                from users
                where email = %s
                limit 1
                """,
                (email,),
            )
            row = await cur.fetchone()
    except Exception as exc:
        raise AuthDatabaseError(
            "Failed to load user."
        ) from exc

    if row is None:
        return None

    return {
        "id": row[0],
        "email": row[1],
        "password_hash": row[2],
        "created_at": row[3],
    }


async def create_user(email: str, password_hash: str) -> dict:
    """Create a new user."""
    try:
        async with await _connect() as conn:
            cur = await conn.execute(
                """
                insert into users (email, password_hash)
                values (%s, %s)
                returning id, email, created_at
                """,
                (email, password_hash),
            )
            row = await cur.fetchone()
    except Exception as exc:
        raise AuthDatabaseError(
            "Failed to create user."
        ) from exc

    return {
        "id": row[0],
        "email": row[1],
        "created_at": row[2],
    }
