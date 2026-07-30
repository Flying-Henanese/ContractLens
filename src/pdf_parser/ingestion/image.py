from __future__ import annotations

from typing import Literal

ImageFormat = Literal["bmp", "jpeg", "png", "tiff", "webp"]


def detect_image_format(content: bytes) -> ImageFormat | None:
    """Return the supported image format identified from its binary signature."""
    if content.startswith(b"BM"):
        return "bmp"
    if content.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if content.startswith((b"II*\x00", b"MM\x00*")):
        return "tiff"
    if len(content) >= 12 and content.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "webp"
    return None
