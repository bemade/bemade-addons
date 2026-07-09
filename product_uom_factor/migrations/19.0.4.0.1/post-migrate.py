# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Migration 19.0.4.0.1: corrective backfill of product.uom.factor.delegate_uom_id.

This migration REPAIRS rows that the 19.0.4.0.0 delegation rework left with a
NULL delegate_uom_id (Odoo #3994). It is NOT merely defensive: the original
19.0.4.0.0/post-migrate.py backfill is structurally unable to find the rows it
was meant to fix, so on any environment that upgraded through 19.0.4.0.0 with
pre-existing product.uom.factor rows, those rows are still NULL.

Why 19.0.4.0.0's backfill failed
--------------------------------
19.0.4.0.0/post-migrate.py iterates `Factor.search([])` and creates a delegate
for each row missing one. But `product.uom.factor` declares
`_inherits = {"uom.uom": "delegate_uom_id"}`, so it inherits uom.uom's `active`
field and the ORM sets `_active_name = 'active'`. Consequently
`BaseModel._search()` auto-injects an implicit `('active', '=', True)` leaf into
EVERY search whose domain doesn't already mention 'active'. Because 'active' is
an inherited field routed through delegate_uom_id, and because a delegate /
inherited Many2one is compiled through an INNER JOIN on the delegate table
(odoo/orm/domains.py:950-954), the resulting SQL effectively ANDs in
"delegate_uom_id IS NOT NULL AND <delegate>.active IS TRUE". So a bare
`Factor.search([])` (and, a fortiori, `Factor.search([('delegate_uom_id','=',
False)])`) can NEVER return a row whose delegate_uom_id is NULL. 19.0.4.0.0's
backfill therefore silently processed zero legacy rows, and the freshly-added
NULL column stayed NULL — which is exactly the persistent "delegate_uom_id
contains null values" state observed on RWI.

Why THIS migration uses raw SQL
-------------------------------
To find the NULL rows we must bypass the ORM's implicit active/delegate filter
entirely. We select the target ids with raw SQL
(`SELECT id FROM product_uom_factor WHERE delegate_uom_id IS NULL`) and
`browse()` them directly, then reuse 19.0.4.0.0's per-row delegate-creation
logic verbatim. The raw-SQL NULL filter is inherently idempotent: once a row is
backfilled it is no longer NULL, so a second run selects nothing.

Do NOT switch this back to an ORM search, and do NOT add a manual NOT NULL /
_sql_constraints here — the field's existing `required=True` makes Odoo re-apply
the DB NOT NULL automatically on a later load once these rows are clean.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — ORM already handled initial creation.
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    Uom = env["uom.uom"]

    # Find NULL-delegate rows via raw SQL. An ORM search on product.uom.factor
    # CANNOT be used here: the model _inherits uom.uom's `active` field, so
    # search() auto-injects an implicit active=True leaf that compiles (through
    # the delegate INNER JOIN, odoo/orm/domains.py:950-954) into
    # "delegate_uom_id IS NOT NULL", silently excluding the very rows we need.
    cr.execute(
        "SELECT id FROM product_uom_factor WHERE delegate_uom_id IS NULL"
    )
    null_ids = [row[0] for row in cr.fetchall()]

    _logger.info(
        "product_uom_factor 19.0.4.0.1 migration: found %d factor row(s) "
        "with NULL delegate_uom_id (19.0.4.0.0 backfill could not reach them)",
        len(null_ids),
    )
    if not null_ids:
        return

    factors = env["product.uom.factor"].browse(null_ids)

    migrated = 0
    for factor in factors:
        base_uom = factor.product_tmpl_id.uom_id
        foreign_uom = factor.foreign_uom_id
        if not base_uom or not foreign_uom:
            _logger.warning(
                "Factor %d missing base_uom or foreign_uom; cannot backfill "
                "delegate_uom_id automatically. Manual review required "
                "(see task 3994 diagnostic).",
                factor.id,
            )
            continue

        # Create the delegated uom.uom — same construction as 19.0.4.0.0.
        delegate = Uom.create(
            {
                "name": foreign_uom.name,
                "relative_uom_id": base_uom.id,
                "relative_factor": factor.factor,
            }
        )
        # Write directly to the column to bypass the _inherits create path.
        cr.execute(
            "UPDATE product_uom_factor SET delegate_uom_id = %s WHERE id = %s",
            (delegate.id, factor.id),
        )
        factor.invalidate_recordset(["delegate_uom_id"])

        # Ensure the product's uom_ids includes the delegate (additive).
        tmpl = factor.product_tmpl_id
        if delegate not in tmpl.uom_ids:
            tmpl.uom_ids = [(4, delegate.id)]

        migrated += 1
        _logger.info(
            "19.0.4.0.1: backfilled factor %d (%s→%s) for product '%s': "
            "created delegate UoM %d",
            factor.id,
            foreign_uom.name,
            base_uom.name,
            factor.product_tmpl_id.name,
            delegate.id,
        )

    _logger.info(
        "product_uom_factor 19.0.4.0.1 migration: backfilled %d/%d NULL row(s)",
        migrated,
        len(null_ids),
    )
