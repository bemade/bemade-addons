"""Backfill of the HEIC attachments stored before the module.

Acceptance criteria:

1.  The backfill cron is shipped inactive.
2.  ``_heic_backfill_domain`` finds plain binary attachments whose mimetype is
    a HEIC one or whose name ends in .heic/.heif, and none other.
3.  A batch converts at most ``batch_size`` attachments in place (content,
    mimetype, name); a failure is flagged ``heic_convert_failed`` and is not
    picked again, so the backfill always ends.
4.  The cron commits after each batch, reports what is left, and deactivates
    itself once nothing is left. Running it again is harmless (idempotent).
"""

import io
from unittest.mock import patch

from PIL import Image

from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import mute_logger

from .common import CORRUPT_HEIC, make_heic, make_png

LOGGER = "odoo.addons.bemade_attachment_heic.models.ir_attachment"


@tagged("post_install", "-at_install")
class TestBackfillCron(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "HEIC Backfill Partner"})
        heic = make_heic()
        Attachment = cls.env["ir.attachment"]
        # Store raw HEIC as it was before the module: bypass the conversion.
        cls.legacy = Attachment
        for i, (name, mimetype) in enumerate(
            [
                ("IMG_1.HEIC", "image/heic"),
                ("IMG_2.heic", "application/octet-stream"),
                ("IMG_3.heif", "image/heif"),
                ("noext", "image/heic"),
            ]
        ):
            cls.legacy |= Attachment.with_context(heic_no_convert=True).create(
                {
                    "name": name,
                    "raw": heic,
                    "mimetype": mimetype,
                    "res_model": "res.partner",
                    "res_id": cls.partner.id,
                }
            )
        cls.broken = Attachment.with_context(heic_no_convert=True).create(
            {
                "name": "broken.heic",
                "raw": CORRUPT_HEIC,
                "res_model": "res.partner",
                "res_id": cls.partner.id,
            }
        )
        cls.png = Attachment.create(
            {
                "name": "green.png",
                "raw": make_png(),
                "res_model": "res.partner",
                "res_id": cls.partner.id,
            }
        )
        cls.cron = cls.env.ref("bemade_attachment_heic.ir_cron_convert_heic_attachments")

    def _candidates(self):
        return self.env["ir.attachment"].sudo().search(
            self.env["ir.attachment"]._heic_backfill_domain()
        )

    def test_cron_ships_inactive(self):
        self.assertFalse(self.cron.active)

    def test_domain(self):
        found = self._candidates()
        self.assertEqual(found & (self.legacy | self.broken | self.png), self.legacy | self.broken)
        self.assertEqual(self.legacy[0].mimetype, "image/heic")

    def test_batch_limit_and_failures(self):
        Attachment = self.env["ir.attachment"]
        with mute_logger(LOGGER):
            done, failed = Attachment._heic_backfill_batch(batch_size=2)
        self.assertEqual(done + failed, 2)
        with mute_logger(LOGGER):
            while Attachment._heic_backfill_count():
                Attachment._heic_backfill_batch(batch_size=2)
        for att in self.legacy:
            self.assertEqual(att.mimetype, "image/jpeg")
            self.assertTrue(att.name.endswith(".jpg"), att.name)
            self.assertEqual(Image.open(io.BytesIO(att.raw)).format, "JPEG")
        self.assertEqual(self.legacy.mapped("name")[3], "noext.jpg")
        self.assertTrue(self.broken.heic_convert_failed)
        self.assertEqual(self.broken.raw, CORRUPT_HEIC)
        self.assertNotIn(self.broken, self._candidates())
        self.assertEqual(self.png.mimetype, "image/png")

    def test_cron_commits_and_deactivates(self):
        calls = []

        def fake_commit_progress(self_cron, processed=0, *, remaining=None, deactivate=False):
            calls.append((processed, remaining, deactivate))
            return 3600.0

        # The cron may find HEIC attachments of other modules' data: count them.
        expected_total = self.env["ir.attachment"]._heic_backfill_count()
        with (
            patch.object(
                type(self.env["ir.cron"]), "_commit_progress", fake_commit_progress
            ),
            mute_logger(LOGGER),
        ):
            self.env["ir.attachment"]._cron_convert_heic_attachments(batch_size=2)
        self.assertGreaterEqual(len(calls), 3)
        self.assertEqual(sum(c[0] for c in calls), expected_total)
        self.assertEqual(calls[-1][1:], (0, True))
        self.assertTrue(all(not c[2] for c in calls[:-1]))
        self.assertEqual(self.env["ir.attachment"]._heic_backfill_count(), 0)
        # Idempotent: a second run finds nothing and changes nothing.
        calls.clear()
        with patch.object(
            type(self.env["ir.cron"]), "_commit_progress", fake_commit_progress
        ):
            self.env["ir.attachment"]._cron_convert_heic_attachments(batch_size=2)
        self.assertEqual(calls, [(0, 0, True)])

    def test_cron_stops_when_out_of_time(self):
        calls = []

        def fake_commit_progress(self_cron, processed=0, *, remaining=None, deactivate=False):
            calls.append((processed, remaining, deactivate))
            return 0.0

        with (
            patch.object(
                type(self.env["ir.cron"]), "_commit_progress", fake_commit_progress
            ),
            mute_logger(LOGGER),
        ):
            self.env["ir.attachment"]._cron_convert_heic_attachments(batch_size=2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0], 2)
        self.assertFalse(calls[0][2])
