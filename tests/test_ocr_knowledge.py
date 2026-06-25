"""Tests for OCR-backed knowledge base imports."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.config import Config
from src.legal.knowledge_base import LocalLegalKnowledgeBase


def test_knowledge_base_loads_ocr_image_when_direct_text_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    image_path = kb_dir / "contract.png"
    image_path.write_bytes(b"fake-image-bytes")

    class FakeOCRReader:
        def extract_text(self, path: Path) -> str:
            assert path == image_path
            return "ocr extracted contract text"

    monkeypatch.setattr("src.legal.knowledge_base.LocalOCRReader", FakeOCRReader)
    monkeypatch.setattr(
        "src.legal.knowledge_base.UnavailableOCRReader", type("FakeUnavailableOCRReader", (), {})
    )
    monkeypatch.setattr(Config, "ENABLE_OCR_FALLBACK", True)
    kb = LocalLegalKnowledgeBase(knowledge_base_dir=kb_dir)
    kb.load()

    docs = [
        doc["text"] for doc in kb._docs if doc.get("metadata", {}).get("source") == "contract.png"
    ]
    assert docs == ["ocr extracted contract text"]


def test_knowledge_base_skips_image_when_ocr_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    kb_dir = tmp_path / "kb"
    kb_dir.mkdir()
    image_path = kb_dir / "contract.png"
    image_path.write_bytes(b"fake-image-bytes")

    class FakeUnavailableOCRReader:
        pass

    monkeypatch.setattr("src.legal.knowledge_base.UnavailableOCRReader", FakeUnavailableOCRReader)
    monkeypatch.setattr(
        "src.legal.knowledge_base.LocalOCRReader", lambda: FakeUnavailableOCRReader()
    )
    monkeypatch.setattr(Config, "ENABLE_OCR_FALLBACK", True)
    kb = LocalLegalKnowledgeBase(knowledge_base_dir=kb_dir)
    kb.load()

    assert all(doc.get("metadata", {}).get("source") != "contract.png" for doc in kb._docs)
