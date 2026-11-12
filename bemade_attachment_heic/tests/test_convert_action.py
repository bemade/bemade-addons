"""« Convert to JPEG » action on a HEIC attachment.

Acceptance criteria:

1.  ``action_convert_heic_to_jpeg`` converts a HEIC attachment in place and
    returns the mail store data of the converted attachment (for the card to
    refresh).
2.  A corrupt HEIC raises a UserError whose message is bilingual, French
    first, and never a traceback; the reason goes to the server log.
3.  A user who cannot write the attachment's record gets an AccessError.
4.  A non-HEIC attachment raises a bilingual UserError.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged
from odoo.tools.misc import mute_logger

from .common import CORRUPT_HEIC, make_heic, make_png

LOGGER = "odoo.addons.bemade_attachment_heic.models.ir_attachment"


@tagged("post_install", "-at_install")
class TestConvertAction(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = new_test_user(cls.env, login="heic_internal", groups="base.group_user,base.group_partner_manager")
        cls.partner = cls.env["res.partner"].create({"name": "HEIC Action Partner"})
        Attachment = cls.env["ir.attachment"].with_context(heic_no_convert=True)
        vals = {"res_model": "res.partner", "res_id": cls.partner.id}
        cls.heic_att = Attachment.create(
            dict(vals, name="IMG_9.HEIC", raw=make_heic(), mimetype="image/heic")
        )
        cls.corrupt_att = Attachment.create(
            dict(vals, name="broken.heic", raw=CORRUPT_HEIC, mimetype="image/heic")
        )
        cls.png_att = Attachment.create(dict(vals, name="green.png", raw=make_png()))

    def test_convert_success(self):
        result = self.heic_att.with_user(self.user).action_convert_heic_to_jpeg()
        self.assertEqual(self.heic_att.mimetype, "image/jpeg")
        self.assertEqual(self.heic_att.name, "IMG_9.jpg")
        stored = result["ir.attachment"]
        self.assertEqual(stored[0]["id"], self.heic_att.id)
        self.assertEqual(stored[0]["mimetype"], "image/jpeg")
        self.assertEqual(stored[0]["name"], "IMG_9.jpg")

    def test_convert_corrupt_bilingual_error(self):
        with (
            self.assertLogs(LOGGER, "WARNING") as logs,
            self.assertRaises(UserError) as err,
        ):
            self.corrupt_att.with_user(self.user).action_convert_heic_to_jpeg()
        message = str(err.exception)
        self.assertTrue(message.startswith("Ce fichier HEIC n'a pas pu être converti"))
        self.assertIn("This HEIC file could not be converted", message)
        self.assertLess(
            message.index("Ce fichier"), message.index("This HEIC file")
        )
        self.assertNotIn("Traceback", message)
        self.assertIn("broken.heic", logs.output[0])
        self.assertEqual(self.corrupt_att.raw, CORRUPT_HEIC)

    def test_convert_no_write_access(self):
        readonly_partner = self.env["res.partner"].create({"name": "Locked"})
        att = self.env["ir.attachment"].with_context(heic_no_convert=True).create(
            {
                "name": "IMG_L.heic",
                "raw": make_heic(),
                "res_model": "res.partner",
                "res_id": readonly_partner.id,
            }
        )
        portal = new_test_user(self.env, login="heic_portal", groups="base.group_portal")
        with mute_logger("odoo.models"), self.assertRaises(AccessError):
            att.with_user(portal).action_convert_heic_to_jpeg()
        self.assertEqual(att.name, "IMG_L.heic")

    def test_not_heic(self):
        with self.assertRaises(UserError) as err:
            self.png_att.with_user(self.user).action_convert_heic_to_jpeg()
        self.assertIn("n'est pas une image HEIC", str(err.exception))
        self.assertIn("is not a HEIC image", str(err.exception))
