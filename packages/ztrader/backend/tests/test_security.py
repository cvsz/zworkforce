# apps/ztrader/backend/tests/test_security.py

import os
# Pre-set required environment variables before importing config / main / security
os.environ["ENCRYPTION_KEY"] = "00000000000000000000000000000000"
os.environ["JWT_SECRET"] = "00000000000000000000000000000000"

import pytest
from ztrader.core.security import encryptor, Encryptor

def test_encryption_decryption_cycle():
    plain_text = "test-secret-value-value-value-value-api-key-12345"

    # Encrypt
    encrypted = encryptor.encrypt(plain_text)
    assert encrypted != plain_text
    assert len(encrypted) > 0

    # Decrypt
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == plain_text

def test_decryption_failure():
    # Corrupt or invalid base64 input should throw ValueError
    with pytest.raises(ValueError):
        encryptor.decrypt("invalid-base-64-ciphertext")

def test_empty_handling():
    assert encryptor.encrypt("") == ""
    assert encryptor.decrypt("") == ""

def test_custom_key_lengths():
    # Test padding / truncation of keys in Encryptor constructor
    short_encryptor = Encryptor()
    assert short_encryptor.key is not None
    assert len(short_encryptor.key) == 32
