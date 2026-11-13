"""« Convert to JPEG » button on a chatter attachment card (smoke tour).

Acceptance criteria:

1.  A HEIC attachment of a message shows a « Convert to JPEG » button; a
    click converts it and the card becomes an image preview of the .jpg.
2.  On a corrupt HEIC the button shows the bilingual (French first) error
    in a notification, not a traceback dialog.

This only smoke-tests the button; the look of the card is reviewed by hand.
"""

from odoo.tests import HttpCase, tagged

from .common import CORRUPT_HEIC, make_heic


@tagged("post_install", "-at_install")
class TestConvertTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "HEIC Tour Partner"})
        Attachment = cls.env["ir.attachment"].with_context(heic_no_convert=True)
        vals = {"res_model": "res.partner", "res_id": cls.partner.id, "mimetype": "image/heic"}
        good = Attachment.create(dict(vals, name="IMG_TOUR.heic", raw=make_heic()))
        bad = Attachment.create(dict(vals, name="BROKEN_TOUR.heic", raw=CORRUPT_HEIC))
        cls.partner.message_post(body="Good photo", attachment_ids=good.ids)
        cls.partner.message_post(body="Bad photo", attachment_ids=bad.ids)
        cls.good = good

    def test_convert_tour(self):
        self.start_tour(
            "/odoo/res.partner/%s" % self.partner.id,
            "bemade_attachment_heic_convert_tour",
            login="admin",
        )
        self.good.invalidate_recordset()
        self.assertEqual(self.good.mimetype, "image/jpeg")
        self.assertEqual(self.good.name, "IMG_TOUR.jpg")
