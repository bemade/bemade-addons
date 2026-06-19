from odoo import models, fields, api


class Company(models.Model):
    _inherit = "res.company"

    warn_supplier_overdue = fields.Boolean(
        string="Warn when supplier invoice overdue",
        default=True,
        help="Warn user when purchasing from a vendor with overdue bills.",
    )

    warn_supplier_overdue_user_type = fields.Selection(
        string="Warned User",
        selection=[
            ("current", "Current User"),
            ("specific", "Specific User"),
        ],
        default="current",
        help="Which user to warn when supplier is overdue",
    )

    warn_supplier_overdue_user_id = fields.Many2one(
        string="User",
        comodel_name="res.users",
        help="Specific User to warn when supplier is overdue.",
    )

    warn_supplier_scope = fields.Selection(
        string="Warning Vendor Scope",
        selection=[
            ("all", "All Vendors"),
            ("specific", "Specific Vendors"),
        ],
        default="all",
        help=(
            "Choose whether to apply overdue warnings to all vendors or only to "
            "specific vendors."
        ),
    )

    warn_supplier_specific_ids = fields.Many2many(
        comodel_name="res.partner",
        domain=[("supplier_rank", ">", 0)],
        string="Specific Vendors",
        help="Select specific vendors to apply overdue invoice warnings.",
    )

    def warn_overdue_for_supplier(self, supplier):
        """Returns true if the current company settings indicate that the user should
        be warned when confirming an order for the given supplier (res.partner)."""
        self.ensure_one()
        return self.warn_supplier_overdue and (
            self.warn_supplier_scope == "all"
            or (
                self.warn_supplier_scope == "specific"
                and supplier in self.warn_supplier_specific_ids
            )
        )
