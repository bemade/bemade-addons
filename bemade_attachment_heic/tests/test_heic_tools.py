"""Pure HEIC helpers.

Acceptance criteria:

1.  HEIC/HEIF content is recognised from its ISO BMFF ``ftyp`` brand (heic,
    heix, hevc, mif1...), AVIF and other formats are not.
2.  ``.heic`` / ``.heif`` file names are recognised, case-insensitively.
3.  ``heic_to_jpeg`` returns a JPEG of the same picture, oriented as it must be
    displayed, with the EXIF orientation reset and other EXIF tags kept.
4.  Content that cannot be decoded raises ``HeicConversionError``.
5.  The converted file name swaps the extension for ``.jpg``.
6.  ``sniff_image_mimetype`` recognises the content of the image formats a
    browser shows (JPEG, PNG, GIF, WebP) and returns None for anything else
    (HEIC, PDF, garbage, empty).
7.  ``relabel_name`` gives a HEIC-labelled name the extension of its real
    format: the HEIC extension is replaced, a name without extension gets one,
    a name already carrying the right extension is kept.
"""

import io

from PIL import Image

from odoo.tests import TransactionCase, tagged

from ..tools import (
    HeicConversionError,
    heic_to_jpeg,
    is_heic_bytes,
    is_heic_name,
    jpeg_name,
    relabel_name,
    sniff_image_mimetype,
)
from .common import (
    CORRUPT_HEIC,
    GARBAGE,
    WEBP_HEADER,
    make_heic,
    make_image,
    make_jpeg,
    make_png,
)


@tagged("post_install", "-at_install")
class TestHeicTools(TransactionCase):
    def test_magic_bytes(self):
        self.assertTrue(is_heic_bytes(make_heic()))
        for brand in (b"heic", b"heix", b"hevc", b"heim", b"heis", b"mif1", b"msf1"):
            head = b"\x00\x00\x00\x18ftyp" + brand + b"\x00\x00\x00\x00mif1heic"
            self.assertTrue(is_heic_bytes(head), brand)
        avif = b"\x00\x00\x00\x1cftypavif\x00\x00\x00\x00avifmif1miaf"
        self.assertFalse(is_heic_bytes(avif))
        avif_generic = b"\x00\x00\x00\x1cftypmif1\x00\x00\x00\x00mif1avifmiaf"
        self.assertFalse(is_heic_bytes(avif_generic))
        self.assertFalse(is_heic_bytes(make_png()))
        self.assertFalse(is_heic_bytes(b""))
        self.assertFalse(is_heic_bytes(None))

    def test_names(self):
        for name in ("IMG_0001.heic", "IMG_0001.HEIC", "photo.heif", "a.b.HeIf"):
            self.assertTrue(is_heic_name(name), name)
        for name in ("photo.jpg", "heic.pdf", "", None, "photo.heic.txt"):
            self.assertFalse(is_heic_name(name), name)
        self.assertEqual(jpeg_name("IMG_0001.HEIC"), "IMG_0001.jpg")
        self.assertEqual(jpeg_name("photo.heif"), "photo.jpg")
        self.assertEqual(jpeg_name("upload"), "upload.jpg")
        self.assertEqual(jpeg_name(""), "image.jpg")

    def test_convert_landscape(self):
        jpeg = heic_to_jpeg(make_heic(40, 20))
        img = Image.open(io.BytesIO(jpeg))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(img.size, (40, 20))
        red, _g, blue = img.convert("RGB").getpixel((2, 10))
        self.assertGreater(red, 200)
        self.assertLess(blue, 60)

    def test_convert_applies_orientation(self):
        """EXIF orientation 6 (rotate 90° clockwise): the red left half ends on top."""
        jpeg = heic_to_jpeg(make_heic(40, 20, orientation=6))
        img = Image.open(io.BytesIO(jpeg))
        self.assertEqual(img.size, (20, 40))
        top = img.convert("RGB").getpixel((10, 2))
        bottom = img.convert("RGB").getpixel((10, 37))
        self.assertGreater(top[0], 200)
        self.assertGreater(bottom[2], 200)
        exif = img.getexif()
        self.assertIn(exif.get(0x0112), (None, 1))
        self.assertEqual(exif.get(0x010F), "Synthetic Camera")

    def test_convert_corrupt(self):
        with self.assertRaises(HeicConversionError):
            heic_to_jpeg(CORRUPT_HEIC)
        with self.assertRaises(HeicConversionError):
            heic_to_jpeg(make_png())
        with self.assertRaises(HeicConversionError):
            heic_to_jpeg(b"")

    def test_sniff_image_mimetype(self):
        self.assertEqual(sniff_image_mimetype(make_jpeg()), "image/jpeg")
        self.assertEqual(sniff_image_mimetype(make_png()), "image/png")
        self.assertEqual(sniff_image_mimetype(make_image("GIF")), "image/gif")
        self.assertEqual(sniff_image_mimetype(WEBP_HEADER), "image/webp")
        for raw in (make_heic(), CORRUPT_HEIC, GARBAGE, b"%PDF-1.4\n", b"", None):
            self.assertIsNone(sniff_image_mimetype(raw), raw[:16] if raw else raw)

    def test_relabel_name(self):
        self.assertEqual(relabel_name("x.HEIC", "image/jpeg"), "x.jpg")
        self.assertEqual(relabel_name("x.heif", "image/png"), "x.png")
        self.assertEqual(relabel_name("x.heic", "image/gif"), "x.gif")
        self.assertEqual(relabel_name("x.HEIC", "image/webp"), "x.webp")
        self.assertEqual(relabel_name("upload", "image/png"), "upload.png")
        self.assertEqual(relabel_name("", "image/png"), "image.png")
        self.assertEqual(relabel_name(None, "image/jpeg"), "image.jpg")
        self.assertEqual(relabel_name("photo.jpeg", "image/jpeg"), "photo.jpeg")
        self.assertEqual(relabel_name("photo.PNG", "image/png"), "photo.PNG")
