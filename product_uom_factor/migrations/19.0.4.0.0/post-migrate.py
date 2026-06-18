# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Migration 19.0.4.0.0: Rework product.uom.factor to delegation design.

For each existing product.uom.factor row:
1. Create a delegated uom.uom record (relative_uom_id=base, relative_factor=factor)
2. Link it via delegate_uom_id
3. Ensure the product template's uom_ids includes the delegated UoM (additive)

Also rewrites any existing transaction lines that used the global foreign UoM
(e.g. the generic mL) for a product that now has a factor-specific delegated UoM.
This is idempotent: lines already pointing to the delegate are skipped.

On Verajet (greenfield), no transaction lines exist, so the rewrite is trivial.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Fresh install — ORM already handled initial creation
        return

    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})

    Factor = env['product.uom.factor']
    Uom = env['uom.uom']

    factors = Factor.search([])
    _logger.info(
        "product_uom_factor 19.0.4.0.0 migration: processing %d factor rows",
        len(factors),
    )

    migrated = 0
    for factor in factors:
        # Skip if delegate already exists (idempotent)
        if factor.delegate_uom_id and factor.delegate_uom_id.id:
            _logger.debug("Factor %d already has delegate %d, skipping", factor.id, factor.delegate_uom_id.id)
            continue

        base_uom = factor.product_tmpl_id.uom_id
        foreign_uom = factor.foreign_uom_id  # renamed from uom_id
        if not base_uom or not foreign_uom:
            _logger.warning("Factor %d missing base_uom or foreign_uom, skipping", factor.id)
            continue

        # Create the delegated uom.uom
        delegate = Uom.create({
            'name': foreign_uom.name,
            'relative_uom_id': base_uom.id,
            'relative_factor': factor.factor,
        })
        # Write directly to the column to bypass the _inherits create path
        cr.execute(
            "UPDATE product_uom_factor SET delegate_uom_id = %s WHERE id = %s",
            (delegate.id, factor.id),
        )
        factor.invalidate_recordset(['delegate_uom_id'])

        # Ensure the product's uom_ids includes the delegate (additive)
        tmpl = factor.product_tmpl_id
        if delegate not in tmpl.uom_ids:
            tmpl.uom_ids = [(4, delegate.id)]

        migrated += 1
        _logger.info(
            "Migrated factor %d (%s→%s) for product '%s': created delegate UoM %d",
            factor.id, foreign_uom.name, base_uom.name,
            factor.product_tmpl_id.name, delegate.id,
        )

    _logger.info(
        "product_uom_factor 19.0.4.0.0 migration: migrated %d/%d factor rows",
        migrated, len(factors),
    )

    # Rewrite transaction lines: any line using the GLOBAL foreign UoM for a
    # factored product should now point to the product's delegate UoM.
    # This ensures stored quantities remain correct (they were computed with the
    # old context-injection approach; the factor value is the same, so stored
    # base-UoM quantities don't change — only the line UoM reference changes).
    _rewrite_transaction_line_uoms(env)


def _rewrite_transaction_line_uoms(env):
    """Rewrite transaction lines from global foreign UoM → product factor-UoM.

    For each factor row, find lines where:
    - product_id matches the factor's product template variants
    - product_uom_id = the global foreign_uom_id (e.g. generic mL)

    And update them to use the delegate UoM instead.
    Idempotent: lines already pointing to the delegate are skipped.
    """
    cr = env.cr
    Factor = env['product.uom.factor']

    line_models = [
        ('sale.order.line', 'product_uom_id', 'product_id'),
        ('purchase.order.line', 'product_uom_id', 'product_id'),
        ('account.move.line', 'product_uom_id', 'product_id'),
        ('stock.move', 'product_uom', 'product_id'),
        ('stock.move.line', 'product_uom_id', 'product_id'),
        ('mrp.bom.line', 'product_uom_id', 'product_id'),
    ]

    for factor in Factor.search([('delegate_uom_id', '!=', False)]):
        foreign_uom_id = factor.foreign_uom_id.id
        delegate_uom_id = factor.delegate_uom_id.id
        if not foreign_uom_id or not delegate_uom_id:
            continue

        product_ids = factor.product_tmpl_id.product_variant_ids.ids
        if not product_ids:
            continue

        for model_name, uom_field, product_field in line_models:
            try:
                Model = env[model_name]
            except KeyError:
                continue  # module not installed

            table = Model._table
            cr.execute(
                f"""
                UPDATE {table}
                SET {uom_field} = %s
                WHERE {uom_field} = %s
                  AND {product_field} = ANY(%s)
                """,
                (delegate_uom_id, foreign_uom_id, product_ids),
            )
            if cr.rowcount:
                _logger.info(
                    "Rewrote %d %s lines: UoM %d → delegate %d (factor %d)",
                    cr.rowcount, model_name, foreign_uom_id, delegate_uom_id, factor.id,
                )
