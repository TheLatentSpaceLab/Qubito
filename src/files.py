"""Unified file-reading utilities for text, PDF, and images."""

from __future__ import annotations

import re
from pathlib import Path

_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


def read_file(path: Path) -> str:
    """Read a file and return its text content.

    Supports plain text, PDF (via pymupdf), and images (via OCR).

    Raises
    ------
    FileNotFoundError
        If *path* does not exist.
    ValueError
        If the file type is not supported or cannot be decoded.
    """
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {path}")

    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _read_pdf(path)
    if suffix in _IMAGE_EXTENSIONS:
        return _read_image(path)
    return _read_text(path)


def _read_pdf(path: Path) -> str:
    """Extract text from a PDF using pymupdf."""
    import pymupdf

    doc = pymupdf.open(str(path))
    pages: list[str] = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()

    if not pages:
        raise ValueError(f"No readable text in PDF: {path}")
    return "\n\n".join(pages)


def _read_image(path: Path) -> str:
    """Extract text from an image via OCR."""
    from src.ocr.reader import Reader

    return Reader().extract_image_information(str(path))


def _read_text(path: Path) -> str:
    """Read a plain-text file."""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(f"Cannot read file as UTF-8: {path}") from exc


def extract_file_paths(text: str) -> list[Path]:
    """Find file paths referenced in a text string.

    Detects absolute paths (``/home/...``) and ``~/...`` paths with
    a file extension.  Only returns paths that exist on disk.
    """
    pattern = r'(~?/(?:[\w.\-]+/)*[\w.\-]+\.\w{1,5})'
    candidates = re.findall(pattern, text)
    paths: list[Path] = []
    seen: set[str] = set()
    for raw in candidates:
        expanded = Path(raw.strip()).expanduser()
        if not expanded.is_absolute():
            expanded = Path.cwd() / expanded
        key = str(expanded)
        if key not in seen and expanded.is_file():
            seen.add(key)
            paths.append(expanded)
    return paths
