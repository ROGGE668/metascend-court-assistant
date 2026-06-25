"""Local OCR module for optional image/PDF text extraction.

This module intentionally stays out of the realtime ASR main path. It is only
used when evidence or knowledge-base imports need to recover text from files
that do not expose readable text directly, such as scanned PDFs, screenshots,
photos, or photographed documents.

The default implementation requires the optional local dependencies:

* ``paddlepaddle``
* ``paddleocr``
* ``pymupdf``
* ``pdf2image``

If any required optional dependency is unavailable, the module degrades
gracefully so the existing import paths keep working without a hard crash.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from src.config import Config

logger = logging.getLogger(__name__)


class UnavailableOCRReader:
    """Fallback OCR reader that reports missing optional dependencies."""

    def extract_text(self, path: Path) -> str:
        raise RuntimeError(
            "本地 OCR 依赖未安装，无法提取扫描件/图片文字。"
            "请在支持安装依赖的环境运行："
            "`uv pip install --system --python .venv/bin/python paddlepaddle paddleocr pymupdf pdf2image`。"
        )


class LocalOCRReader:
    """Best-effort local OCR reader for image and scanned PDF inputs."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        self.cache_dir = cache_dir or Config.MODEL_CACHE_DIR / "ocr"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._available = self._check_dependencies()

    def extract_text(self, path: Path) -> str:
        """Extract text from an image or PDF via optional local OCR."""
        path = Path(path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(f"OCR input not found: {path}")
        if not Config.ENABLE_OCR_FALLBACK:
            raise RuntimeError(
                "当前已禁用 OCR 回退；如需解析扫描件，请先在设置中开启 OCR。"
            )
        if not self._available:
            raise RuntimeError(
                "本地 OCR 依赖不可用，无法解析该文件。"
                "请安装可选依赖：paddlepaddle / paddleocr / pymupdf / pdf2image。"
            )
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            return self._extract_pdf(path)
        return self._extract_image(path)

    def _check_dependencies(self) -> bool:
        missing: list[str] = []
        for module in ("paddle", "paddleocr", "fitz", "pdf2image"):
            try:
                __import__(module)
            except Exception as exc:  # pragma: no cover - optional dependency path
                logger.debug("Optional OCR dependency missing: %s (%s)", module, exc)
                missing.append(module)
        if missing:
            logger.warning("Optional OCR dependencies unavailable: %s", ", ".join(missing))
            return False
        return True

    def _extract_pdf(self, path: Path) -> str:
        from pdf2image import convert_from_path
        import fitz

        text = ""
        try:
            doc = fitz.open(path)
            for page_number in range(len(doc)):
                page = doc.load_page(page_number)
                page_text = page.get_text("text").strip()
                if page_text:
                    text += page_text + "\n\n"
                else:
                    page_images = convert_from_path(
                        path,
                        first_page=page_number + 1,
                        last_page=page_number + 1,
                        dpi=220,
                    )
                    for image in page_images:
                        page_text = self._extract_image_bytes(self._pil_to_bytes(image))
                        if page_text:
                            text += page_text + "\n\n"
        except Exception as exc:
            logger.debug("PDF OCR extraction failed for %s: %s", path, exc)
        return text.strip()

    def _extract_image(self, path: Path) -> str:
        from PIL import Image

        try:
            with Image.open(path) as image:
                return self._extract_image_bytes(self._pil_to_bytes(image))
        except Exception as exc:
            logger.debug("Image OCR extraction failed for %s: %s", path, exc)
            return ""

    @staticmethod
    def _pil_to_bytes(image: Any) -> bytes:
        from io import BytesIO

        buffer = BytesIO()
        fmt = image.format or "PNG"
        if fmt.upper() == "TIF":
            fmt = "PNG"
        image.save(buffer, format=fmt)
        return buffer.getvalue()

    def _extract_image_bytes(self, data: bytes) -> str:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(
            use_angle_cls=True,
            lang="ch",
            show_log=False,
        )
        try:
            result = ocr.ocr(img=data, cls=True)
        except Exception as exc:
            logger.debug("PaddleOCR failed on image bytes: %s", exc)
            return ""
        finally:
            try:
                ocr.close()
            except Exception:
                pass
        lines: list[str] = []
        try:
            for page in result or []:
                if not page:
                    continue
                for line in page:
                    text = (line[1][0] if len(line) > 1 else "").strip()
                    if text:
                        lines.append(text)
        except Exception as exc:
            logger.debug("OCR result parsing failed: %s", exc)
        return "\n".join(lines)
