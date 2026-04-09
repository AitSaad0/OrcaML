"""
Part 5 — JWT token tests
These tests do NOT need a database or running server.
"""
from src.auth.security.tokens import create_access_token, decode_access_token


def test_token_contains_user_id():
    token = create_access_token("user-123")
    decoded = decode_access_token(token)
    assert decoded == "user-123"


def test_tampered_token_returns_none():
    token = create_access_token("user-123")
    bad_token = token[:-5] + "XXXXX"
    assert decode_access_token(bad_token) is None


def test_garbage_token_returns_none():
    assert decode_access_token("not.a.valid.token") is None


def test_empty_token_returns_none():
    assert decode_access_token("") is None


def test_different_users_get_different_tokens():
    t1 = create_access_token("user-1")
    t2 = create_access_token("user-2")
    assert t1 != t2
    assert decode_access_token(t1) == "user-1"
    assert decode_access_token(t2) == "user-2"
