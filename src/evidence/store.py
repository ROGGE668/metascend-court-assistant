"""Local evidence file store.

Keeps copies of user-imported evidence files under ``data/evidence/``.
This MVP store keeps files as-is; encryption can be layered later via
``src.utils.encryption`` if needed.
"""

import logging
from pathlib import Path
import shutil
from datetime import datetime, timezone

from src.config import Config

logger = logging.getLogger(__name__)


class EvidenceStore:
    """Manage imported evidence files on disk."""

    def __init__(self, base_dir: Path | None = None) -> None:
        self.base_dir = base_dir or Config.DATA_DIR / "evidence"
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def path(self, name: str) -> Path:
        """Return the absolute path for an evidence file by name."""
        return (self.base_dir / name).resolve()

    def list(self) -> list[dict]:
        """Return metadata for every stored evidence file."""
        items: list[dict] = []
        for path in sorted(self.base_dir.iterdir()):
            if not path.is_file():
                continue
            stat = path.stat()
            text_preview = self._read_preview(path)
            items.append(
                {
                    "name": path.name,
                    "size": stat.st_size,
                    "suffix": path.suffix.lower(),
                    "modified_at": datetime.fromtimestamp(
                        stat.st_mtime, tz=timezone.utc
                    ).isoformat(),
                    "ocr_status": "disabled" if not Config.ENABLE_OCR_FALLBACK else ("available" if self._ocr_available() else "unavailable"),
                    "text_preview": text_preview,
                }
            )
        return items

    def _read_preview(self, path: Path) -> str:
        try:
            text = self.extract_text(path)
        except Exception as exc:
            logger.debug("Preview extraction failed for %s: %s", path, exc)
            text = ""
        return text[:220]

    def _ocr_available(self) -> bool:
        try:
            from src.ocr.engine import LocalOCRReader

            return LocalOCRReader()._available
        except Exception:
            return False

    def import_file(self, src: Path | str) -> Path:
        """Copy an external file into the evidence store.

        If a file with the same name already exists, a numeric suffix is
        appended to avoid overwriting.
        """
        src_path = Path(src).expanduser().resolve()
        if not src_path.exists():
            raise FileNotFoundError(f"Evidence file not found: {src_path}")
        if not src_path.is_file():
            raise ValueError(f"Not a file: {src_path}")

        dest = self.base_dir / src_path.name
        if dest.exists():
            stem = src_path.stem
            suffix = src_path.suffix
            counter = 1
            while True:
                candidate = self.base_dir / f"{stem}_{counter}{suffix}"
                if not candidate.exists():
                    dest = candidate
                    break
                counter += 1

        shutil.copy2(src_path, dest)
        logger.info("Imported evidence: %s -> %s", src_path, dest)
        return dest

    def extract_text(self, path: Path | str) -> str:
        """Try to read text from an imported evidence file.

        Plain text files are returned directly. Image or scanned PDF files
        trigger optional OCR only when the local OCR dependencies are
        available; otherwise the method returns an empty string and logs a
        warning instead of crashing the import flow.
        """
        src_path = Path(path).expanduser().resolve()
        if not src_path.exists() or not src_path.is_file():
            return ""

        suffix = src_path.suffix.lower()
        try:
            if suffix == ".pdf":
                return self._read_pdf_text(src_path)
            if suffix in {".txt", ".md", ".json", ".yaml", ".yml", ".csv"}:
                return src_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as exc:
            logger.warning("Evidence text extraction failed for %s: %s", src_path, exc)

        if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp"}:
            try:
                return self._run_optional_ocr(src_path)
            except Exception as exc:
                logger.warning("Evidence OCR failed for %s: %s", src_path, exc)
                return ""

        return ""

    def _read_pdf_text(self, path: Path) -> str:
        from src.ocr.engine import UnavailableOCRReader

        try:
            import fitz
        except Exception as exc:
            logger.debug("PyMuPDF unavailable for %s: %s", path, exc)
            raise RuntimeError("pdf_text_unavailable") from exc

        try:
            doc = fitz.open(path)
            chunks: list[str] = []
            for page in doc:
                text = page.get_text("text").strip()
                if text:
                    chunks.append(text)
            return "\n\n".join(chunks).strip()
        except Exception as exc:
            logger.debug("Direct PDF text extraction failed for %s: %s", path, exc)
            raise RuntimeError("pdf_text_unavailable") from exc

    @staticmethod
    def _run_optional_ocr(path: Path) -> str:
        from src.ocr.engine import LocalOCRReader, UnavailableOCRReader

        reader = LocalOCRReader()
        if isinstance(reader, UnavailableOCRReader):
            return ""
        return reader.extract_text(path)

    def delete(self, name: str) -> None:
        """Delete an evidence file by name."""
        target = self.path(name)
        # Safety: refuse to delete anything outside the evidence base dir.
        if not str(target).startswith(str(self.base_dir)):
            raise ValueError(f"Invalid evidence name: {name}")
        if target.exists():
            target.unlink()
            logger.info("Deleted evidence: %s", target)
