"""Tests for the evidence store module."""

from pathlib import Path

import pytest

from src.evidence.store import EvidenceStore
from src.ocr.engine import LocalOCRReader, UnavailableOCRReader


def test_evidence_list_empty(tmp_path: Path):
    store = EvidenceStore(base_dir=tmp_path)
    assert store.list() == []


def test_evidence_import_and_list(tmp_path: Path):
    store = EvidenceStore(base_dir=tmp_path)
    src = tmp_path / "source" / "contract.pdf"
    src.parent.mkdir()
    src.write_text("contract content")

    dest = store.import_file(src)
    assert dest.name == "contract.pdf"
    assert dest.exists()

    items = store.list()
    assert len(items) == 1
    assert items[0]["name"] == "contract.pdf"
    assert items[0]["size"] == len("contract content")
    assert items[0]["suffix"] == ".pdf"


def test_evidence_import_duplicate_renames(tmp_path: Path):
    store = EvidenceStore(base_dir=tmp_path)
    src = tmp_path / "source" / "receipt.jpg"
    src.parent.mkdir()
    src.write_text("receipt")

    store.import_file(src)
    dest2 = store.import_file(src)

    assert dest2.name == "receipt_1.jpg"
    names = {item["name"] for item in store.list()}
    assert names == {"receipt.jpg", "receipt_1.jpg"}


def test_evidence_delete(tmp_path: Path):
    store = EvidenceStore(base_dir=tmp_path)
    src = tmp_path / "source" / "audio.m4a"
    src.parent.mkdir()
    src.write_bytes(b"audio data")
    store.import_file(src)

    store.delete("audio.m4a")
    assert store.list() == []


def test_evidence_delete_invalid_name(tmp_path: Path):
    store = EvidenceStore(base_dir=tmp_path)
    with pytest.raises(ValueError):
        store.delete("../config.py")


def test_evidence_path(tmp_path: Path):
    store = EvidenceStore(base_dir=tmp_path)
    assert store.path("x.txt") == (tmp_path / "x.txt").resolve()


def test_evidence_ocr_fallback_extracts_image_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = EvidenceStore(base_dir=tmp_path)
    src = tmp_path / "scan.png"
    src.write_bytes(b"image")

    class FakeOCRReader:
        def extract_text(self, path: Path) -> str:
            assert path == src
            return "ocr text"

    monkeypatch.setattr("src.ocr.engine.LocalOCRReader", FakeOCRReader)
    monkeypatch.setattr("src.ocr.engine.UnavailableOCRReader", type("FakeUnavailableOCRReader", (), {}))
    monkeypatch.setattr(store, "import_file", lambda src: src)
    text = store.extract_text(src)
    assert text == "ocr text"


def test_evidence_ocr_fallback_returns_empty_when_unavailable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = EvidenceStore(base_dir=tmp_path)
    src = tmp_path / "scan.png"
    src.write_bytes(b"image")
    monkeypatch.setattr("src.ocr.engine.LocalOCRReader", lambda: UnavailableOCRReader())
    assert store.extract_text(src) == ""


def test_evidence_txt_does_not_call_ocr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    store = EvidenceStore(base_dir=tmp_path)
    src = tmp_path / "notes.txt"
    src.write_text("plain text", encoding="utf-8")

    class ExplodingOCRReader:
        def extract_text(self, path: Path) -> str:
            raise AssertionError("纯文本不应走到 OCR")

    monkeypatch.setattr("src.ocr.engine.LocalOCRReader", ExplodingOCRReader)
    monkeypatch.setattr("src.ocr.engine.UnavailableOCRReader", type("FakeUnavailableOCRReader", (), {}))
    assert store.extract_text(src) == "plain text"


