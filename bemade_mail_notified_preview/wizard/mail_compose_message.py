# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
from odoo import api, fields, models
from odoo.exceptions import AccessError

# Recipient fields of the OCA module mail_composer_cc_bcc, used when installed.
_CC_BCC_FIELDS = ("partner_cc_ids", "partner_bcc_ids")


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    notified_followers_preview = fields.Char(
        string="Followers notified",
        compute="_compute_notified_followers_preview",
        help="Followers of the record that this message will also notify. "
        "Display only.",
    )

    def _notified_preview_depends(self):
        return [
            "composition_mode",
            "composition_batch",
            "model",
            "res_ids",
            "subtype_id",
            "subtype_is_log",
            "partner_ids",
        ] + [fname for fname in _CC_BCC_FIELDS if fname in self._fields]

    @api.depends(lambda self: self._notified_preview_depends())
    def _compute_notified_followers_preview(self):
        for composer in self:
            composer.notified_followers_preview = (
                composer._get_notified_followers_preview()
            )

    def _get_notified_followers_preview(self):
        self.ensure_one()
        if (
            not self.model
            or self.composition_mode != "comment"
            or self.composition_batch
            or self.subtype_is_log
        ):
            return False
        if self.model not in self.env:
            return False
        Model = self.env[self.model]
        if not hasattr(Model, "_notified_preview_followers"):
            return False
        res_ids = self._evaluate_res_ids()
        if len(res_ids) != 1 or not res_ids[0]:
            return False
        record = Model.browse(res_ids).exists()
        if not record:
            return False
        recipients = self.partner_ids
        for fname in _CC_BCC_FIELDS:
            if fname in self._fields:
                recipients |= self[fname]
        try:
            followers = record._notified_preview_followers(
                exclude_partner_ids=recipients._origin.ids,
                subtype_id=self.subtype_id.id or None,
            )
        except AccessError:
            return False
        return record._notified_preview_line(followers)
