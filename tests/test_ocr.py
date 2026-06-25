"""Tests for the optional local OCR module."""

from pathlib import Path

import pytest

from src.ocr.engine import LocalOCRReader, UnavailableOCRReader


def test_unavailable_reader_raises_with_install_hint():
    reader = UnavailableOCRReader()
    with pytest.raises(RuntimeError, match="uv pip install --system --python .venv/bin/python"):
        reader.extract_text(Path("fake.png"))


def test_local_reader_missing_dependencies_reports_unavailable(tmp_path: Path):
    fake = tmp_path / "scan.pdf"
    fake.write_text("pdf")
    reader = LocalOCRReader()
    reader._available = False
    with pytest.raises(RuntimeError, match="paddlepaddle / paddleocr / pymupdf / pdf2image"):
        reader.extract_text(fake)


def test_local_reader_missing_input_raises_file_not_found(tmp_path: Path):
    missing = tmp_path / "missing.png"
    reader = LocalOCRReader()
    with pytest.raises(FileNotFoundError, match="OCR input not found"):
        reader.extract_text(missing)


def test_local_reader_respects_disabled_ocr_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fake = tmp_path / "scan.pdf"
    fake.write_text("pdf")
    reader = LocalOCRReader()
    reader._available = True
    monkeypatch.setenv("ENABLE_OCR_FALLBACK", "false")
    monkeypatch.setattr("src.config.Config.ENABLE_OCR_FALLBACK", False)
    with pytest.raises(RuntimeError, match="当前已禁用 OCR 回退"):
        reader.extract_text(fake)
