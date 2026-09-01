# apps/ztrader/backend/src/ztrader/core/security.py

import os
import base64
import logging
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from ztrader.core.config import settings

logger = logging.getLogger("ztrader.security")

class Encryptor:
    def __init__(self):
        # We need a 32-byte key for AES-256.
        # The key is expected to be a hex-encoded or base64-encoded string in config.
        raw_key = settings.ENCRYPTION_KEY.encode("utf-8")

        # Try decoding hex first, then base64, fallback to padding if it's a simple string (e.g. tests)
        try:
            self.key = bytes.fromhex(settings.ENCRYPTION_KEY)
        except ValueError:
            try:
                self.key = base64.b64decode(raw_key)
            except Exception:
                self.key = raw_key

        # Enforce key length to be exactly 32 bytes for AES-256
        if len(self.key) < 32:
            self.key = (self.key * 32)[:32]
        elif len(self.key) > 32:
            self.key = self.key[:32]

        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plain_text: str) -> str:
        if not plain_text:
            return ""
        # 12-byte nonce for GCM
        nonce = os.urandom(12)
        encrypted_bytes = self.aesgcm.encrypt(nonce, plain_text.encode("utf-8"), None)
        # Combine nonce and encrypted ciphertext, then encode to base64 string
        combined = nonce + encrypted_bytes
        return base64.b64encode(combined).decode("utf-8")

    def decrypt(self, encrypted_text: str) -> str:
        if not encrypted_text:
            return ""
        try:
            combined = base64.b64decode(encrypted_text.encode("utf-8"))
            if len(combined) < 12:
                raise ValueError("Ciphertext too short")
            nonce = combined[:12]
            ciphertext = combined[12:]
            decrypted_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to decrypt data: {e}")
            raise ValueError("Decryption failed. Invalid key or corrupted data.")

# Global encryptor instance
encryptor = Encryptor()
