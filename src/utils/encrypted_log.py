"""Encrypted log file handler using AES-256-GCM."""

import base64
import logging
from pathlib import Path

from src.utils.encryption import AESCipher


class EncryptedLogFileHandler(logging.Handler):
    """Write each log record as a base64-encoded AES-256-GCM line."""

    def __init__(
        self,
        filename: str | Path,
        password: str | None = None,
    ):
        super().__init__()
        self.filename = Path(filename)
        self.filename.parent.mkdir(parents=True, exist_ok=True)
        self.cipher = AESCipher(password)
        # Append in binary mode; each record is one base64 line.
        self._file = open(self.filename, "ab")

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            encrypted = self.cipher.encrypt(msg.encode("utf-8"))
            self._file.write(base64.b64encode(encrypted) + b"\n")
            self._file.flush()
        except Exception:
            self.handleError(record)

    def close(self) -> None:
        if hasattr(self, "_file") and not self._file.closed:
            self._file.close()
        super().close()


def decrypt_log_file(path: str | Path, password: str | None = None) -> list[str]:
    """Decrypt an encrypted log file and return the plaintext lines."""
    cipher = AESCipher(password)
    lines = []
    with open(path, "rb") as fp:
        for line in fp:
            line = line.strip()
            if not line:
                continue
            decrypted = cipher.decrypt(base64.b64decode(line))
            lines.append(decrypted.decode("utf-8"))
    return lines
