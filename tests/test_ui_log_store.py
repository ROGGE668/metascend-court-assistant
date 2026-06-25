"""Tests for the in-memory app log store."""

from __future__ import annotations

import logging

import pytest

from src.ui.log_store import AppLogStore


def _make_record(level: str, message: str) -> logging.LogRecord:
    record = logging.LogRecord(
        name="src.pipeline",
        level=getattr(logging, level.upper(), logging.INFO),
        pathname="src/pipeline.py",
        lineno=10,
        msg=message,
        args=(),
        exc_info=None,
    )
    return record


def test_recent_logs_return_entries() -> None:
    store = AppLogStore(maxlen=10)
    store.handle(_make_record("INFO", "loaded asr"))
    store.handle(_make_record("ERROR", "audio failed"))
    logs = store.recent()
    assert len(logs) == 2
    assert logs[0]["level"] == "INFO"
    assert logs[-1]["message"] == "audio failed"


def test_recent_logs_respects_limit() -> None:
    store = AppLogStore(maxlen=50)
    for index in range(25):
        store.handle(_make_record("INFO", f"tick {index}"))
    logs = store.recent(limit=10)
    assert len(logs) == 10
    assert logs[0]["message"] == "tick 15"


def test_recent_logs_clears_entries() -> None:
    store = AppLogStore(maxlen=50)
    store.handle(_make_record("INFO", "one"))
    store.clear()
    assert store.recent() == []
