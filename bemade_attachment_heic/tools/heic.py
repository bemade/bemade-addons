# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""HEIC/HEIF detection and conversion to JPEG, independent of the ORM."""

import io
import logging
import os

from PIL import ImageOps

_logger = logging.getLogger(__name__)

try:
    import pillow_heif
except ImportError:  # the module stays usable: uploads are just not converted
    pillow_heif = None

HEIC_MIMETYPES = (
    "image/heic",
    "image/heif",
    "image/heic-sequence",
    "image/heif-sequence",
)
HEIC_EXTENSIONS = (".heic", ".heif")
# ISO BMFF major brands of HEIF files coded with HEVC (what iPhones produce).
HEIC_BRANDS = {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs"}
# Generic HEIF brands: also used by AVIF, which browsers display natively.
GENERIC_BRANDS = {b"mif1", b"msf1"}
AVIF_BRANDS = {b"avif", b"avis"}
JPEG_QUALITY = 90

_missing_logged = False


class HeicConversionError(Exception):
    """The content could not be converted from HEIC to JPEG."""


def is_heic_bytes(raw):
    """Tell whether ``raw`` starts like a HEIC/HEIF file (``ftyp`` box)."""
    if not raw or len(raw) < 12 or raw[4:8] != b"ftyp":
        return False
    major = raw[8:12]
    if major in HEIC_BRANDS:
        return True
    if major in GENERIC_BRANDS:
        box_size = int.from_bytes(raw[0:4], "big")
        compatible = raw[16 : min(box_size, 64)]
        brands = {compatible[i : i + 4] for i in range(0, len(compatible) - 3, 4)}
        return not brands & AVIF_BRANDS
    return False


def is_heic_name(name):
    return bool(name) and name.lower().endswith(HEIC_EXTENSIONS)


def jpeg_name(name):
    """``IMG_0001.HEIC`` -> ``IMG_0001.jpg``; a name without HEIC extension gets ``.jpg``."""
    if not name:
        return "image.jpg"
    if is_heic_name(name):
        name = os.path.splitext(name)[0]
    return f"{name}.jpg"


def decoder_available():
    global _missing_logged
    if pillow_heif is None and not _missing_logged:
        _missing_logged = True
        _logger.warning(
            "pillow-heif is not installed: HEIC attachments are not converted to JPEG."
        )
    return pillow_heif is not None


def heic_to_jpeg(raw, quality=JPEG_QUALITY):
    """Return ``raw`` (HEIC/HEIF bytes) converted to JPEG bytes.

    The picture is turned upright (container transforms and EXIF orientation),
    the EXIF orientation is then reset and the other EXIF tags kept.

    :raises HeicConversionError: decoder missing or content not decodable.
    """
    if not decoder_available():
        raise HeicConversionError("the pillow-heif decoder is not installed")
    if not raw:
        raise HeicConversionError("empty file")
    try:
        heif = pillow_heif.open_heif(raw, convert_hdr_to_8bit=True)
        image = heif.to_pillow()
        image = ImageOps.exif_transpose(image)
        exif = image.info.get("exif") or b""
        if image.mode != "RGB":
            image = image.convert("RGB")
        out = io.BytesIO()
        image.save(out, "JPEG", quality=quality, exif=exif)
    except Exception as e:  # noqa: BLE001 - any decoder failure means "not convertible"
        raise HeicConversionError(str(e) or e.__class__.__name__) from e
    return out.getvalue()


__all__ = [
    "HEIC_MIMETYPES",
    "HeicConversionError",
    "heic_to_jpeg",
    "is_heic_bytes",
    "is_heic_name",
    "jpeg_name",
]
