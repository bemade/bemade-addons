"""HEIC uploads are stored as JPEG.

Acceptance criteria:

1.  An attachment created with HEIC content is stored as a JPEG: content,
    ``mimetype`` ``image/jpeg`` and a ``.jpg`` name, whether the browser sent
    ``image/heic``, ``application/octet-stream`` with a ``.heic`` name, or
    nothing but the bytes (magic-byte detection).
2.  Writing HEIC content on an existing attachment converts it the same way.
3.  Inbound email attachments (``message_post`` with attachments) and
    chatter uploads both go through this path.
4.  Non-HEIC uploads are byte-identical.
5.  A corrupt HEIC upload is kept as is (never blocks the upload) and a
    warning is logged.
6.  Binary-field attachments (``res_field`` set) are left alone.
"""

import base64
import io
from unittest.mock import patch

from PIL import Image

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from .common import CORRUPT_HEIC, make_heic, make_png


@tagged("post_install", "-at_install")
class TestAttachmentUpload(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "HEIC Upload Partner"})
        cls.heic = make_heic()

    def _create(self, **vals):
        values = {"res_model": "res.partner", "res_id": self.partner.id}
        values.update(vals)
        return self.env["ir.attachment"].create(values)

    def assertIsJpeg(self, attachment, name):
        self.assertEqual(attachment.mimetype, "image/jpeg")
        self.assertEqual(attachment.name, name)
        img = Image.open(io.BytesIO(attachment.raw))
        self.assertEqual(img.format, "JPEG")
        self.assertEqual(attachment.file_size, len(attachment.raw))
        self.assertFalse(attachment.heic_convert_failed)

    def test_heic_mimetype(self):
        att = self._create(name="IMG_0001.HEIC", raw=self.heic, mimetype="image/heic")
        self.assertIsJpeg(att, "IMG_0001.jpg")

    def test_octet_stream_with_heic_name(self):
        att = self._create(
            name="IMG_0002.heic",
            datas=base64.b64encode(self.heic),
            mimetype="application/octet-stream",
        )
        self.assertIsJpeg(att, "IMG_0002.jpg")

    def test_magic_bytes_only(self):
        att = self._create(name="upload", raw=self.heic)
        self.assertIsJpeg(att, "upload.jpg")

    def test_write_heic_content(self):
        att = self._create(name="scan.png", raw=make_png())
        att.write({"name": "IMG_0003.heic", "datas": base64.b64encode(self.heic)})
        self.assertIsJpeg(att, "IMG_0003.jpg")

    def test_write_raw_without_name_renames(self):
        att = self.env["ir.attachment"].with_context(heic_no_convert=True).create(
            {
                "name": "IMG_0004.heic",
                "raw": b"placeholder",
                "res_model": "res.partner",
                "res_id": self.partner.id,
            }
        ).with_context(heic_no_convert=False)
        att.write({"raw": self.heic})
        self.assertIsJpeg(att, "IMG_0004.jpg")

    def test_message_post_attachment(self):
        """Inbound email / chatter post with an attachment tuple."""
        message = self.partner.message_post(
            body="Photo", attachments=[("IMG_0005.HEIC", self.heic)]
        )
        self.assertIsJpeg(message.attachment_ids, "IMG_0005.jpg")

    def test_non_heic_untouched(self):
        png = make_png()
        att = self._create(name="green.png", raw=png)
        self.assertEqual(att.raw, png)
        self.assertEqual(att.mimetype, "image/png")
        pdf = b"%PDF-1.4\n%synthetic\n"
        att = self._create(name="doc.pdf", raw=pdf)
        self.assertEqual(att.raw, pdf)
        self.assertEqual(att.name, "doc.pdf")

    def test_corrupt_heic_kept(self):
        with self.assertLogs(
            "odoo.addons.bemade_attachment_heic.models.ir_attachment", "WARNING"
        ) as logs:
            att = self._create(name="broken.heic", raw=CORRUPT_HEIC)
        self.assertEqual(att.raw, CORRUPT_HEIC)
        self.assertEqual(att.name, "broken.heic")
        self.assertIn("broken.heic", logs.output[0])

    @mute_logger(
        "odoo.addons.bemade_attachment_heic.models.ir_attachment",
        "odoo.addons.bemade_attachment_heic.tools.heic",
    )
    def test_decoder_missing_kept(self):
        heic_tools = "odoo.addons.bemade_attachment_heic.tools.heic"
        with (
            patch(f"{heic_tools}.pillow_heif", None),
            patch(f"{heic_tools}._missing_logged", False),
        ):
            att = self._create(name="IMG_0006.heic", raw=self.heic)
        self.assertEqual(att.raw, self.heic)
        self.assertEqual(att.name, "IMG_0006.heic")

    def test_binary_field_untouched(self):
        att = self._create(
            name="IMG_0007.heic", raw=self.heic, res_field="comment"
        )
        self.assertEqual(att.raw, self.heic)
        self.assertEqual(att.name, "IMG_0007.heic")
