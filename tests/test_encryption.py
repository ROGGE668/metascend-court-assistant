"""Tests for AES-256-GCM encryption utilities."""

import pytest

from src.utils.encryption import AESCipher


def test_encrypt_decrypt_roundtrip():
    cipher = AESCipher(password="my-secret-password")
    plaintext = b"courtroom recording segment"
    encrypted = cipher.encrypt(plaintext)
    assert encrypted != plaintext
    decrypted = cipher.decrypt(encrypted)
    assert decrypted == plaintext


def test_wrong_password_fails():
    cipher1 = AESCipher(password="correct-password")
    encrypted = cipher1.encrypt(b"sensitive data")
    cipher2 = AESCipher(password="wrong-password")
    with pytest.raises(Exception):
        cipher2.decrypt(encrypted)


def test_generate_password():
    password = AESCipher.generate_password()
    assert len(password) == 32
    assert password != AESCipher.generate_password()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
