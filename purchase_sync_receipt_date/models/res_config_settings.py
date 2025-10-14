# Copyright 2025 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0)

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    purchase_sync_receipt_date = fields.Boolean(
        string="Sync Receipt Scheduled Date",
        related="company_id.purchase_sync_receipt_date",
        readonly=False,
        help="When enabled, updating the expected date on a purchase order line "
        "will automatically update the scheduled date on the related receipt.",
    )
