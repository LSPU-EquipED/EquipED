"""apps/server/tests/training_data/test_tokens.py"""

from __future__ import annotations

from server.modules.training_data.tokens import generate_raw_token, hash_token


def test_generate_raw_token_is_url_safe_and_long_enough():
    token = generate_raw_token()
    assert len(token) >= 32
    assert all(c.isalnum() or c in "-_" for c in token)


def test_generate_raw_token_is_unique():
    tokens = {generate_raw_token() for _ in range(100)}
    assert len(tokens) == 100


def test_hash_token_is_deterministic_sha256_hex():
    raw = "fixed-value-for-hashing"
    first = hash_token(raw)
    second = hash_token(raw)
    assert first == second
    assert len(first) == 64
    assert all(c in "0123456789abcdef" for c in first)


def test_hash_token_differs_for_different_input():
    assert hash_token("a") != hash_token("b")
