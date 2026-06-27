"""AES-256-GCM encryption helpers for local recordings and logs."""

import base64
import logging
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class AESCipher:
    """Encrypt/decrypt bytes with AES-256-GCM using a password-derived key."""

    SALT_LEN = 16
    NONCE_LEN = 12
    KEY_LEN = 32
    ITERATIONS = 480_000

    def __init__(self, password: str | None = None):
        self._password = (password or os.getenv("RECORDING_PASSWORD", "")).encode("utf-8")
        if not self._password:
            logger.warning("No RECORDING_PASSWORD set; using a default key (not secure)")
            self._password = b"metascend-default-change-me"

    def _derive_key(self, salt: bytes) -> bytes:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=self.KEY_LEN,
            salt=salt,
            iterations=self.ITERATIONS,
        )
        return kdf.derive(self._password)

    def encrypt(self, plaintext: bytes) -> bytes:
        """Return salt + nonce + ciphertext."""
        salt = os.urandom(self.SALT_LEN)
        nonce = os.urandom(self.NONCE_LEN)
        key = self._derive_key(salt)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return salt + nonce + ciphertext

    def decrypt(self, encrypted: bytes) -> bytes:
        """Decrypt data produced by ``encrypt``."""
        if len(encrypted) < self.SALT_LEN + self.NONCE_LEN:
            raise ValueError("Encrypted data is too short")
        salt = encrypted[: self.SALT_LEN]
        nonce = encrypted[self.SALT_LEN : self.SALT_LEN + self.NONCE_LEN]
        ciphertext = encrypted[self.SALT_LEN + self.NONCE_LEN :]
        key = self._derive_key(salt)
        return AESGCM(key).decrypt(nonce, ciphertext, None)

    @staticmethod
    def generate_password(length: int = 32) -> str:
        """Generate a URL-safe random password."""
        return base64.urlsafe_b64encode(os.urandom(length)).decode("ascii")[:length]
