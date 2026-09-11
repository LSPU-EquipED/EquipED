"""Cryptographic helpers for password, token, and OTP hashing."""

from __future__ import annotations

import hashlib
import hmac
import secrets

SCRYPT_PREFIX = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 64


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_DKLEN,
    )
    return "$".join(
        (
            SCRYPT_PREFIX,
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            salt.hex(),
            derived_key.hex(),
        )
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n_value, r_value, p_value, salt_hex, digest_hex = stored_hash.split(
            "$", 5
        )
    except ValueError:
        return False

    if algorithm != SCRYPT_PREFIX:
        return False

    try:
        expected_digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n_value),
            r=int(r_value),
            p=int(p_value),
            dklen=len(bytes.fromhex(digest_hex)),
        )
    except (TypeError, ValueError):
        return False

    return hmac.compare_digest(expected_digest.hex(), digest_hex)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _otp_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


__all__ = [
    "SCRYPT_DKLEN",
    "SCRYPT_N",
    "SCRYPT_P",
    "SCRYPT_PREFIX",
    "SCRYPT_R",
    "_otp_hash",
    "hash_password",
    "hash_session_token",
    "verify_password",
]
