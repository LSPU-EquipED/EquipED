"""apps/server/modules/training_data/tokens.py"""

from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTES = 32


def generate_raw_token() -> str:
    """Generate a URL-safe opaque token. Never persisted in raw form."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(raw_token: str) -> str:
    """Hash a raw token for at-rest storage and comparison."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


__all__ = ["TOKEN_BYTES", "generate_raw_token", "hash_token"]
