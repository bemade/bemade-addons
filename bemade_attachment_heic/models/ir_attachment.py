# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

from odoo.addons.mail.tools.discuss import Store

from ..tools import (
    HEIC_MIMETYPES,
    HeicConversionError,
    heic_to_jpeg,
    is_heic_bytes,
    is_heic_name,
    jpeg_name,
)

_logger = logging.getLogger(__name__)

BACKFILL_BATCH_SIZE = 50


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    heic_convert_failed = fields.Boolean(
        string="HEIC Conversion Failed",
        readonly=True,
        copy=False,
        help="This HEIC image could not be converted to JPEG; the backfill skips it.",
    )

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------
    @api.model
    def _heic_is_heic(self, raw, mimetype=None, name=None):
        return bool(
            is_heic_bytes(raw)
            or (mimetype and mimetype.lower() in HEIC_MIMETYPES)
            or is_heic_name(name)
        )

    def _heic_is_candidate(self):
        """Tell whether this stored attachment holds a HEIC image."""
        self.ensure_one()
        return (
            self.type == "binary"
            and not self.res_field
            and (
                self._heic_is_heic(None, self.mimetype, self.name)
                or is_heic_bytes(self.raw[:64] if self.raw else b"")
            )
        )

    # ------------------------------------------------------------------
    # Conversion on create / write
    # ------------------------------------------------------------------
    def _check_contents(self, values):
        return super()._check_contents(self._heic_convert_values(values))

    def _heic_convert_values(self, values):
        """Return ``values`` with HEIC content replaced by JPEG.

        A conversion failure keeps the original content: an upload is never
        blocked because of this module.
        """
        if self.env.context.get("heic_no_convert"):
            return values
        if values.get("res_field") or any(self.mapped("res_field")):
            return values  # binary fields keep what their widget gave them
        if values.get("raw"):
            raw = values["raw"]
        elif values.get("datas"):
            raw = base64.b64decode(values["datas"])
        else:
            return values
        name = values.get("name") or (len(self) == 1 and self.name) or ""
        if not self._heic_is_heic(raw, values.get("mimetype"), name):
            return values
        try:
            jpeg = heic_to_jpeg(raw)
        except HeicConversionError as e:
            _logger.warning(
                "HEIC attachment %r (ids %s) kept as uploaded, conversion to JPEG failed: %s",
                name,
                self.ids,
                e,
            )
            return values
        if self:
            # write(): core uses the returned dict, and fs_attachment passes the
            # same dict to each record's write, so leave the caller's intact.
            # create() (no record) keeps using the dict of its vals_list.
            values = dict(values)
        if values.get("raw"):
            values["raw"] = jpeg
        else:
            values["datas"] = base64.b64encode(jpeg)
        values["mimetype"] = "image/jpeg"
        values["name"] = jpeg_name(name)
        _logger.info(
            "HEIC attachment %r converted to JPEG (%d -> %d bytes)",
            name,
            len(raw),
            len(jpeg),
        )
        return values

    def _heic_convert_to_jpeg(self):
        """Convert this stored HEIC attachment in place.

        :raises HeicConversionError: the content could not be converted.
        """
        self.ensure_one()
        jpeg = heic_to_jpeg(self.raw)
        self.write(
            {
                "raw": jpeg,
                "mimetype": "image/jpeg",
                "name": jpeg_name(self.name),
                "heic_convert_failed": False,
            }
        )

    # ------------------------------------------------------------------
    # Manual action (chatter button)
    # ------------------------------------------------------------------
    def _heic_error_message(self, reason):
        if reason == "not_heic":
            return self.env._(
                "Ce fichier n'est pas une image HEIC : il n'y a rien à convertir.\n\n"
                "This file is not a HEIC image: there is nothing to convert."
            )
        return self.env._(
            "Ce fichier HEIC n'a pas pu être converti : fichier corrompu ou format "
            "non pris en charge. Téléchargez-le et convertissez-le sur votre appareil."
            "\n\n"
            "This HEIC file could not be converted: the file is corrupt or its "
            "format is not supported. Download it and convert it on your device."
        )

    def action_convert_heic_to_jpeg(self):
        """Convert HEIC attachments to JPEG, for the « Convert to JPEG » button.

        The user must be allowed to write the attachments (i.e. their record).
        Returns the mail store data of the converted attachments.
        """
        self.check_access("write")
        for attachment in self:
            if not attachment._heic_is_candidate():
                raise UserError(self._heic_error_message("not_heic"))
            try:
                attachment._heic_convert_to_jpeg()
            except HeicConversionError as e:
                _logger.warning(
                    "Manual conversion of HEIC attachment %r (id %s) failed: %s",
                    attachment.name,
                    attachment.id,
                    e,
                )
                raise UserError(self._heic_error_message("failed")) from e
        return Store().add(self).get_result()

    # ------------------------------------------------------------------
    # Backfill cron
    # ------------------------------------------------------------------
    @api.model
    def _heic_backfill_domain(self):
        return [
            ("type", "=", "binary"),
            ("res_field", "=", False),
            ("heic_convert_failed", "=", False),
            "|",
            "|",
            ("mimetype", "in", list(HEIC_MIMETYPES)),
            ("name", "=ilike", "%.heic"),
            ("name", "=ilike", "%.heif"),
        ]

    @api.model
    def _heic_backfill_count(self):
        return self.sudo().search_count(self._heic_backfill_domain())

    @api.model
    def _heic_backfill_batch(self, batch_size=BACKFILL_BATCH_SIZE):
        """Convert up to ``batch_size`` stored HEIC attachments.

        A failed one is flagged so that it is not picked again.
        :return: (converted count, failed count)
        """
        attachments = self.sudo().search(
            self._heic_backfill_domain(), limit=batch_size, order="id"
        )
        done = failed = 0
        for attachment in attachments:
            try:
                attachment._heic_convert_to_jpeg()
                done += 1
            except HeicConversionError as e:
                failed += 1
                attachment.heic_convert_failed = True
                _logger.warning(
                    "HEIC backfill: attachment %r (id %s) could not be converted: %s",
                    attachment.name,
                    attachment.id,
                    e,
                )
        return done, failed

    @api.model
    def _cron_convert_heic_attachments(self, batch_size=BACKFILL_BATCH_SIZE):
        """Convert the HEIC attachments stored before this module, batch by batch.

        Commits after each batch; deactivates the cron once none is left.
        """
        IrCron = self.env["ir.cron"]
        total_done = total_failed = 0
        while True:
            done, failed = self._heic_backfill_batch(batch_size)
            total_done += done
            total_failed += failed
            remaining = self._heic_backfill_count()
            time_left = IrCron._commit_progress(
                done + failed, remaining=remaining, deactivate=not remaining
            )
            if not remaining or not (done + failed) or time_left <= 0:
                break
        _logger.info(
            "HEIC backfill: %d converted, %d failed in this run, %d left",
            total_done,
            total_failed,
            remaining,
        )
