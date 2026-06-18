# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
"""Pre-migration 19.0.4.0.0: rename the foreign-unit column.

In the delegation rework the field ``product.uom.factor.uom_id`` (the foreign
unit, e.g. mL) was renamed to ``foreign_uom_id``. Renaming the column here —
before the ORM loads the new model definition — preserves the existing values
so the post-migration can create the matching delegate UoMs. Without this, the
ORM would add a fresh (NULL) ``foreign_uom_id`` column and orphan ``uom_id``.

Guarded so it is a no-op on fresh installs or if already renamed.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute(
        """
        SELECT
            (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'product_uom_factor' AND column_name = 'uom_id'),
            (SELECT 1 FROM information_schema.columns
             WHERE table_name = 'product_uom_factor' AND column_name = 'foreign_uom_id')
        """
    )
    has_old, has_new = cr.fetchone()
    if has_old and not has_new:
        _logger.info(
            "product_uom_factor 19.0.4.0.0: renaming column "
            "product_uom_factor.uom_id -> foreign_uom_id"
        )
        cr.execute(
            "ALTER TABLE product_uom_factor RENAME COLUMN uom_id TO foreign_uom_id"
        )
