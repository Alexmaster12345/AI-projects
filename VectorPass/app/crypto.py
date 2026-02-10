from __future__ import annotations

import secrets

from argon2.low_level import Type, hash_secret_raw
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def derive_key_from_password(password: str, salt: bytes) -> bytes:
    # Argon2id parameters tuned for server-side interactive use.
    # Adjust as needed based on your hardware and latency budget.
    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=2,
        memory_cost=102400,  # 100 MiB
        parallelism=8,
        hash_len=32,
        type=Type.ID,
    )


def encrypt_aesgcm(key: bytes, plaintext: bytes, aad: bytes) -> tuple[bytes, bytes]:
    nonce = secrets.token_bytes(12)
    aesgcm = AESGCM(key)
    cipher = aesgcm.encrypt(nonce, plaintext, aad)
    return nonce, cipher


def decrypt_aesgcm(key: bytes, nonce: bytes, cipher: bytes, aad: bytes) -> bytes:
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, cipher, aad)
