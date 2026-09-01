"""// ZeaZDev [Backend Security Crypto Service] //
// Project: Auto Bot Trader i18n //
// Version: 1.0.0 (Omega Scaffolding) //
// Author: ZeaZDev Meta-Intelligence (Generated) //
// --- DO NOT EDIT HEADER --- //"""

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _load_key() -> bytes:
    """Load and validate the AES-GCM key when encryption is actually used."""
    encryption_key = os.getenv("ENCRYPTION_KEY")
    if not encryption_key:
        raise RuntimeError("ENCRYPTION_KEY not set")

    try:
        raw_key = base64.b64decode(encryption_key, validate=True)
    except Exception as exc:
        raise RuntimeError("ENCRYPTION_KEY must be valid base64") from exc

    if len(raw_key) not in (16, 24, 32):
        raise RuntimeError("ENCRYPTION_KEY must decode to 128/192/256-bit")
    return raw_key


def encrypt_data(plaintext: str):
    aesgcm = AESGCM(_load_key())
    iv = os.urandom(12)
    ct = aesgcm.encrypt(iv, plaintext.encode(), None)
    return base64.b64encode(ct).decode(), base64.b64encode(iv).decode()


def decrypt_data(ciphertext_b64: str, iv_b64: str):
    aesgcm = AESGCM(_load_key())
    ciphertext = base64.b64decode(ciphertext_b64)
    iv = base64.b64decode(iv_b64)
    pt = aesgcm.decrypt(iv, ciphertext, None)
    return pt.decode()
