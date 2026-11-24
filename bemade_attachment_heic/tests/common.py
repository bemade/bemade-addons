import io

from PIL import Image

try:
    import pillow_heif
except ImportError:  # pragma: no cover - the manifest requires it
    pillow_heif = None


def make_heic(width=40, height=20, orientation=None, quality=90):
    """Return the bytes of a small synthetic HEIC image.

    The left half is red and the right half blue, so a test can tell how the
    picture was rotated. ``orientation`` sets the EXIF orientation tag.
    """
    img = Image.new("RGB", (width, height), (255, 0, 0))
    img.paste((0, 0, 255), (width // 2, 0, width, height))
    kwargs = {"quality": quality}
    if orientation:
        exif = Image.Exif()
        exif[0x0112] = orientation
        exif[0x010F] = "Synthetic Camera"
        kwargs["exif"] = exif.tobytes()
    buf = io.BytesIO()
    pillow_heif.from_pillow(img).save(buf, **kwargs)
    return buf.getvalue()


def make_png(width=8, height=8):
    return make_image("PNG", width, height)


def make_image(fmt, width=8, height=8):
    """Return the bytes of a small synthetic image in Pillow format ``fmt``."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (0, 128, 0)).save(buf, fmt)
    return buf.getvalue()


def make_jpeg(width=8, height=8):
    return make_image("JPEG", width, height)


# Starts like a HEIC file (ISO BMFF "ftypheic" box) but holds no image.
CORRUPT_HEIC = b"\x00\x00\x00\x18ftypheic\x00\x00\x00\x00mif1heic" + b"\x00" * 64
# Start of a WebP file (RIFF container, "WEBPVP8 " chunk): enough to sniff its
# type, and does not need a Pillow built with WebP support.
WEBP_HEADER = b"RIFF\x24\x00\x00\x00WEBPVP8 \x18\x00\x00\x00" + b"\x00" * 24
# Neither HEIC nor any image format: what a broken upload may contain.
GARBAGE = b"\x13\x37\x00\xfe" * 32
