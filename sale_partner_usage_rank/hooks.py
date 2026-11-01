# Copyright 2026 Bemade Inc. <marc@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
from odoo.tools import SQL

from .models.res_partner import SLOT_RANKS


def _backfill_sale_usage_ranks(env):
    """Set every partner's sales usage counters from existing orders."""
    env["sale.order"].flush_model(list(SLOT_RANKS))
    for slot, rank in SLOT_RANKS.items():
        env.cr.execute(SQL(
            """
            UPDATE res_partner p
               SET %(rank)s = coalesce(c.uses, 0)
              FROM res_partner p2
              LEFT JOIN (SELECT %(slot)s AS partner_id, count(*) AS uses
                           FROM sale_order GROUP BY %(slot)s) c
                     ON c.partner_id = p2.id
             WHERE p2.id = p.id
               AND p.%(rank)s IS DISTINCT FROM coalesce(c.uses, 0)
            """,
            rank=SQL.identifier(rank), slot=SQL.identifier(slot),
        ))
    env["res.partner"].invalidate_model(list(SLOT_RANKS.values()))
