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
        """ORDER BY terms for ``slot``'s dropdown, most relevant first.

        Address slots with a customer contact: what that contact used and
        what its company owns come before any other company's partners; then
        the slot's preferred partners; then uses with the contact; then uses
        overall.
        """
        self.env["sale.order"].flush_model([slot, "partner_id"])
        self.flush_model([SLOT_RANKS[slot], "type", "commercial_partner_id"])
        partner_id = SQL.identifier(self._table, "id")
        contact_id = self.env.context.get("default_parent_id")
        contact = (
            self.browse(contact_id).exists()
            if slot != "partner_id" and isinstance(contact_id, int) and contact_id
            else self.browse()
        )
        terms = []
        if contact:
            used_with_contact = SQL(
                "(SELECT count(*) FROM sale_order so WHERE so.%s = %s AND so.partner_id = %s)",
                SQL.identifier(slot), partner_id, contact.id,
            )
            terms.append(SQL(
                "(%s = %s OR %s > 0) DESC",
                SQL.identifier(self._table, "commercial_partner_id"),
                contact.commercial_partner_id.id,
                used_with_contact,
            ))
        if (eligible := self._sale_usage_eligible_sql(slot, self._table)) is not None:
            terms.append(SQL("(%s) IS TRUE DESC", eligible))
        if contact:
            terms.append(SQL("%s DESC", used_with_contact))
        terms.append(SQL("%s DESC", SQL.identifier(self._table, SLOT_RANKS[slot])))
        return SQL(", ").join(terms)

    def _sale_usage_eligible_sql(self, slot, alias):
        """The partners ``slot`` prefers, as an SQL condition on ``alias``.

        They come first in the slot's dropdown, and only they become its
        default. None (here) means every partner. Override per slot.
        """
        return None

    def _sale_usage_default_address(self, slot):
        """The address this customer contact uses most in ``slot``.

        First among the addresses on this contact's own orders, then among
        the addresses of its company on anyone's orders. Ties go to the most
        recent order; archived addresses, and any the slot does not prefer
        (``_sale_usage_eligible_sql``), are skipped. Empty when neither
        has a used address.
        """
        self.ensure_one()
        self.env["sale.order"].flush_model([slot, "partner_id"])
        self.flush_model(["active", "commercial_partner_id", "type"])
        for scope in (
            SQL("so.partner_id = %s", self.id),
            SQL("a.commercial_partner_id = %s", self.commercial_partner_id.id),
        ):
            self.env.cr.execute(SQL(
                """
                SELECT so.%(slot)s
                  FROM sale_order so
                  JOIN res_partner a ON a.id = so.%(slot)s
                 WHERE a.active AND %(scope)s AND %(eligible)s
                 GROUP BY so.%(slot)s
                 ORDER BY count(*) DESC, max(so.id) DESC
                 LIMIT 1
                """,
                slot=SQL.identifier(slot), scope=scope,
                eligible=self._sale_usage_eligible_sql(slot, "a") or SQL("TRUE"),
            ))
            if row := self.env.cr.fetchone():
                return self.browse(row[0])
        return self.browse()

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
