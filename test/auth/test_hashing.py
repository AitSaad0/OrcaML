"""
Part 3 — Password hashing tests
These tests do NOT need a database or running server.
"""
from src.auth.security.hashing import hash_password, verify_password


def test_hash_is_not_plain_password():
    h = hash_password("Secret123")
    assert h != "Secret123"


def test_correct_password_verifies():
    h = hash_password("Secret123")
    assert verify_password("Secret123", h) is True


def test_wrong_password_fails():
    h = hash_password("Secret123")
    assert verify_password("WrongPass", h) is False


def test_same_password_produces_different_hashes():
    """bcrypt uses a random salt — same input, different output each time."""
    h1 = hash_password("Secret123")
    h2 = hash_password("Secret123")
    assert h1 != h2


def test_both_hashes_still_verify():
    """Even though hashes differ, both must verify correctly."""
    h1 = hash_password("Secret123")
    h2 = hash_password("Secret123")
    assert verify_password("Secret123", h1) is True
    assert verify_password("Secret123", h2) is True
