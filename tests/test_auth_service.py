import os

import pytest

pytest.importorskip("bcrypt")
pytest.importorskip("jwt")

from backend.services.auth_service import create_access_token, decode_access_token, hash_password, verify_password


def test_password_is_hashed_and_verified():
    password_hash = hash_password("correct horse battery staple")
    assert password_hash != "correct horse battery staple"
    assert verify_password("correct horse battery staple", password_hash)
    assert not verify_password("wrong password", password_hash)


def test_jwt_round_trip_and_tamper_rejection(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    token, _ = create_access_token("user-1")
    assert decode_access_token(token) == "user-1"
    with pytest.raises(Exception):
        decode_access_token(f"{token}x")
