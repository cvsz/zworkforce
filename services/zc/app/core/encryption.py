from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os
from typing import Optional, Tuple

class EndToEndEncryptor:
    """
    AES-GCM based End-to-End Encryption for sensitive telemetry and payloads.
    Uses 256-bit keys and generates a unique nonce for each encryption.
    """
    def __init__(self, key_b64: Optional[str] = None):
        if not key_b64:
            # Fallback to env var or generate a deterministic key for testing
            key_b64 = os.getenv("E2E_SECRET_KEY", base64.b64encode(os.urandom(32)).decode('utf-8'))
        
        self.key = base64.b64decode(key_b64)
        if len(self.key) != 32:
            raise ValueError("AES-GCM requires a 32-byte (256-bit) key")
        
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, plaintext: bytes, associated_data: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Encrypts data and returns (ciphertext, nonce)"""
        nonce = os.urandom(12)  # 96-bit nonce is standard for GCM
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, associated_data)
        return ciphertext, nonce

    def decrypt(self, ciphertext: bytes, nonce: bytes, associated_data: Optional[bytes] = None) -> bytes:
        """Decrypts data using the provided nonce."""
        return self.aesgcm.decrypt(nonce, ciphertext, associated_data)

    def encrypt_string(self, text: str) -> str:
        """Convenience method to encrypt a string into a base64 combined format: nonce:ciphertext"""
        ciphertext, nonce = self.encrypt(text.encode('utf-8'))
        return f"{base64.b64encode(nonce).decode('utf-8')}:{base64.b64encode(ciphertext).decode('utf-8')}"

    def decrypt_string(self, token: str) -> str:
        """Convenience method to decrypt a string from base64 combined format: nonce:ciphertext"""
        try:
            nonce_b64, cipher_b64 = token.split(':', 1)
            nonce = base64.b64decode(nonce_b64)
            ciphertext = base64.b64decode(cipher_b64)
            plaintext = self.decrypt(ciphertext, nonce)
            return plaintext.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Failed to decrypt: {str(e)}")

# Global singleton for application use
e2e_encryptor = EndToEndEncryptor()
