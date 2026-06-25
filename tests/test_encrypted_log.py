"""Tests for encrypted log file handler."""

import logging
import uuid

import pytest

from src.utils.encrypted_log import EncryptedLogFileHandler, decrypt_log_file


def test_encrypted_log_handler(tmp_path):
    log_path = tmp_path / "app.log.enc"
    handler = EncryptedLogFileHandler(log_path, "test-password")
    logger = logging.getLogger(f"test_encrypted_log_{uuid.uuid4().hex[:8]}")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)

    logger.info("hello encrypted log")
    logger.removeHandler(handler)
    handler.close()

    lines = decrypt_log_file(log_path, "test-password")
    assert any("hello encrypted log" in line for line in lines)

    with pytest.raises(Exception):
        decrypt_log_file(log_path, "wrong-password")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
