# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Migration 19.0.4.0.1: defensive re-backfill of product.uom.factor.delegate_uom_id.

This is a safety-net migration for Odoo #3994. The 19.0.4.0.0 delegation
rework (see migrations/19.0.4.0.0/post-migrate.py) backfills delegate_uom_id
for every pre-existing product.uom.factor row, but any row whose base UoM
(product_tmpl_id.uom_id) or foreign_uom_id was itself empty at that time was
logged and skipped, leaving delegate_uom_id NULL.

Since delegate_uom_id is `required=True` (the _inherits delegate — see
models/product_uom_factor.py), any residual NULL blocks Odoo from ever
applying the Postgres NOT NULL constraint on this column, which would abort
a future upgrade that tries to enforce it. This migration re-runs the exact
same backfill logic as 19.0.4.0.0 against only the rows still missing a
delegate, so it is a no-op wherever 19.0.4.0.0 already succeeded (i.e. it is
safe to ship regardless of whether RWI prod actually has any residual
nulls — see docs/diagnostics/3994-product-uom-factor-delegate-uom-id-nulls.md
for the UAT query that determines that).

Idempotent: rows that already have a delegate_uom_id are skipped exactly as
in 19.0.4.0.0. Running this migration twice, or on an environment where
19.0.4.0.0 already fully backfilled, changes nothing.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — ORM already handled initial creation.
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    Factor = env["product.uom.factor"]
    Uom = env["uom.uom"]

    factors = Factor.search([("delegate_uom_id", "=", False)])
    _logger.info(
        "product_uom_factor 19.0.4.0.1 migration: found %d factor row(s) "
        "still missing delegate_uom_id",
        len(factors),
    )

    migrated = 0
    for factor in factors:
        # Idempotent guard, mirrors 19.0.4.0.0/post-migrate.py exactly.
        if factor.delegate_uom_id and factor.delegate_uom_id.id:
            _logger.debug(
                "Factor %d already has delegate %d, skipping",
                factor.id,
                factor.delegate_uom_id.id,
            )
            continue

        base_uom = factor.product_tmpl_id.uom_id
        foreign_uom = factor.foreign_uom_id
        if not base_uom or not foreign_uom:
            _logger.warning(
                "Factor %d still missing base_uom or foreign_uom after "
                "19.0.4.0.0; cannot backfill delegate_uom_id automatically. "
                "Manual review required (see task 3994 diagnostic).",
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
            "19.0.4.0.1: migrated factor %d (%s→%s) for product '%s': "
            "created delegate UoM %d",
            factor.id,
            foreign_uom.name,
            base_uom.name,
            factor.product_tmpl_id.name,
            delegate.id,
        )

    _logger.info(
        "product_uom_factor 19.0.4.0.1 migration: migrated %d/%d factor row(s)",
        migrated,
        len(factors),
    )
