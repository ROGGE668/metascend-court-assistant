"""Optional OCR preprocessing for evidence and knowledge import."""

from src.ocr.engine import LocalOCRReader, UnavailableOCRReader

__all__ = ["LocalOCRReader", "UnavailableOCRReader"]
