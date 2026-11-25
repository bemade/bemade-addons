# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from collections import Counter

from odoo import api, fields, models

from odoo.addons.product_cost_source.tools.cost_source import CONFIDENCE_ORDER

from .sale_order_line import CONFIDENCE_SELECTION, SALESMAN


class SaleOrder(models.Model):
    _inherit = "sale.order"

    cost_source_worst = fields.Selection(
        CONFIDENCE_SELECTION,
        string="Weakest Cost Basis",
        compute="_compute_cost_source_summary",
        groups=SALESMAN,
    )
    cost_source_summary = fields.Char(
        string="Cost Basis Summary",
        compute="_compute_cost_source_summary",
        groups=SALESMAN,
        help="Lines whose cost is not firm, counted per level, worst first. "
        "Empty when every line is firm.",
    )

    @api.depends("order_line.cost_source_confidence")
    def _compute_cost_source_summary(self):
        labels = dict(
            self.env["sale.order.line"]
            ._fields["cost_source_confidence"]
            ._description_selection(self.env)
        )
        for order in self:
            levels = [level for level in order.order_line.mapped("cost_source_confidence") if level]
            if not levels:
                order.cost_source_worst = False
                order.cost_source_summary = False
                continue
            order.cost_source_worst = min(levels, key=CONFIDENCE_ORDER.index)
            counts = Counter(levels)
            parts = []
            for level in CONFIDENCE_ORDER:
                if level == "firm" or not counts[level]:
                    continue
                if counts[level] == 1:
                    parts.append(
                        self.env._("%(count)s line %(level)s", count=1, level=labels[level])
                    )
                else:
                    parts.append(
                        self.env._(
                            "%(count)s lines %(level)s",
                            count=counts[level],
                            level=labels[level],
                        )
                    )
            order.cost_source_summary = ", ".join(parts) or False
