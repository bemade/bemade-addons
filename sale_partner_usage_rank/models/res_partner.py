# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo import fields, models
from odoo.tools import SQL

# Sales order partner slot -> the res.partner counter of its uses.
SLOT_RANKS = {
    "partner_id": "sale_contact_rank",
    "partner_shipping_id": "sale_shipping_rank",
    "partner_invoice_id": "sale_invoice_rank",
}


class ResPartner(models.Model):
    _inherit = "res.partner"

    sale_contact_rank = fields.Integer(
        string="Sales Order Customer Uses", default=0, copy=False, readonly=True,
    )
    sale_shipping_rank = fields.Integer(
        string="Sales Order Delivery Uses", default=0, copy=False, readonly=True,
    )
    sale_invoice_rank = fields.Integer(
        string="Sales Order Invoice Uses", default=0, copy=False, readonly=True,
    )

    def _order_to_sql(self, order, query, alias=None, reverse=False):
        """Put the most-used partners first in a sales order dropdown.

        Only for a top-level search in the standard order, with the slot
        named in the context (``sale_usage_rank``, set on the sales order
        fields). The address slots first count uses with the order's
        customer contact, which the sales order form passes as
        ``default_parent_id``.
        """
        sql = super()._order_to_sql(order, query, alias=alias, reverse=reverse)
        slot = self.env.context.get("sale_usage_rank")
        if (
            slot not in SLOT_RANKS
            or reverse
            or (alias or self._table) != self._table
            or (order or self._order) != self._order
        ):
            return sql
        rank_sql = self._sale_usage_rank_order_sql(slot)
        return SQL("%s, %s", rank_sql, sql) if sql else rank_sql

    def _sale_usage_rank_order_sql(self, slot):
        self.env["sale.order"].flush_model([slot, "partner_id"])
        self.flush_model([SLOT_RANKS[slot]])
        rank_sql = SQL("%s DESC", SQL.identifier(self._table, SLOT_RANKS[slot]))
        contact_id = self.env.context.get("default_parent_id")
        if slot == "partner_id" or not isinstance(contact_id, int) or not contact_id:
            return rank_sql
        return SQL(
            "(SELECT count(*) FROM sale_order so"
            " WHERE so.%s = %s AND so.partner_id = %s) DESC, %s",
            SQL.identifier(slot), SQL.identifier(self._table, "id"), contact_id, rank_sql,
        )

    def _recount_sale_usage_ranks(self):
        """Set the three counters of these partners to their actual counts.

        Rows locked by a concurrent transaction are skipped rather than waited
        on, as core does for ``customer_rank``: a busy customer then never
        blocks order entry, and its count is corrected the next time one of
        its orders is touched.
        """
        if not self.ids:
            return
        self.env["sale.order"].flush_model(list(SLOT_RANKS))
        self.env.cr.execute(SQL(
            """
            UPDATE res_partner p
               SET %(sets)s
             WHERE p.id IN (
                   SELECT id FROM res_partner WHERE id = ANY(%(ids)s)
                    ORDER BY id FOR NO KEY UPDATE SKIP LOCKED)
            """,
            sets=SQL(", ").join(
                SQL(
                    "%s = (SELECT count(*) FROM sale_order so WHERE so.%s = p.id)",
                    SQL.identifier(rank), SQL.identifier(slot),
                )
                for slot, rank in SLOT_RANKS.items()
            ),
            ids=list(self.ids),
        ))
        self.invalidate_model(list(SLOT_RANKS.values()))
