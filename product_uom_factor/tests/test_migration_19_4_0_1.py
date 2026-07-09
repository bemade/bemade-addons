# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

"""Test migration 19.0.4.0.1: defensive re-backfill of delegate_uom_id.

Odoo #3994 diagnosed the "delegate_uom_id contains null values" upgrade
warning as the expected transient artifact of the 19.0.4.0.0 delegation
rework (schema-init runs before post-migrate backfills the column). The
19.0.4.0.1 migration is meant as a defensive safety net: it re-runs the
same backfill logic against any row still missing a delegate after
19.0.4.0.0 (e.g. because a prior run's base UoM / foreign UoM was itself
empty).

Acceptance criteria under test (per 02-design.md test plan):
1. A factor row with delegate_uom_id forced NULL gets a delegate uom.uom
   created and delegate_uom_id set, matching the base UoM + factor.
2. Idempotency: running migrate() twice creates no second delegate and
   leaves the row unchanged.
3. No residual NULLs: after migrate(), no product.uom.factor row has an
   empty delegate_uom_id.

FINDING (see task 04-test-report.md "Blockers"): all three tests below
FAIL — not because the test setup is wrong, but because
`migrations/19.0.4.0.1/post-migrate.py`'s own
`Factor.search([("delegate_uom_id", "=", False)])` call structurally can
never match any row, in this test DB or in production. `product.uom.factor`
_inherits uom.uom's `active` field (delegate_uom_id links the two), so
Odoo's default `search()`/`_search()` auto-injects an `active = True`
filter (odoo/orm/models.py `_search`, the `self._active_name` branch)
whenever the domain doesn't already reference 'active'. Because 'active'
is itself an inherited field routed through delegate_uom_id, that implicit
filter compiles to requiring delegate_uom_id to reference an existing,
active uom.uom row — i.e. it ANDs in "delegate_uom_id IS NOT NULL",
directly contradicting the migration's own explicit "delegate_uom_id IS
NULL" condition. The generated SQL (captured while writing this test)
was:

    ... WHERE ("product_uom_factor"."delegate_uom_id" IS NULL
      AND ("product_uom_factor"."delegate_uom_id" IS NOT NULL
           AND "product_uom_factor__delegate_uom_id"."active" IS TRUE))

which is unsatisfiable. Even `Factor.search([])` with NO domain at all
exhibits the same exclusion for any row with a NULL delegate. This means
the search never finds a row to backfill, in this test OR on a real
upgrade, since the migration never passes `active_test=False` and never
adds an explicit `active` leaf to the domain.

The migrate(cr, version) function lives under migrations/19.0.4.0.1/ and
is not part of the installed Python package (migration scripts are loaded
by Odoo's upgrade machinery via file path, not import), so it is loaded
here directly via importlib against the file path relative to this test
module.

Reproducing the pre-backfill NULL state in a fresh test DB additionally
requires dropping the Postgres NOT NULL constraint (rolled back
automatically with the test's DDL/transaction) and clearing the field
from the ORM's `registry.not_null_fields` cache (a global, non-
transactional set, restored via addCleanup) — both mirror the transient
state a legacy row is actually in on a real upgrade, before either
migration's backfill runs.
"""

import importlib.util
import os

from odoo.tests.common import TransactionCase, tagged

_MIGRATION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "migrations",
    "19.0.4.0.1",
    "post-migrate.py",
)


def _load_migrate_function():
    spec = importlib.util.spec_from_file_location(
        "product_uom_factor_migration_19_4_0_1", _MIGRATION_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged("post_install", "-at_install")
class TestMigration19401DelegateBackfill(TransactionCase):
    """Covers the 19.0.4.0.1 defensive delegate_uom_id backfill.

    All three tests currently FAIL due to a real bug in
    migrations/19.0.4.0.1/post-migrate.py (see module docstring):
    ``Factor.search([("delegate_uom_id", "=", False)])`` never matches
    any row because of Odoo's implicit active-record filtering on models
    that inherit an 'active' field via `_inherits`.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.uom_gram = cls.env.ref("uom.product_uom_gram")
        cls.uom_ml = cls.env.ref("uom.product_uom_milliliter")
        cls.migrate = staticmethod(_load_migrate_function())

    def _create_factor_with_null_delegate(self, name="Test Ink - Migration"):
        """Create a normal factor row (auto-creates its delegate via the
        model's create() override), then force delegate_uom_id back to
        NULL — reproducing the transient state of a pre-existing row the
        instant after 19.0.4.0.0's schema-init ran but before its
        post-migrate backfill executed.
        """
        registry = self.env.registry
        field = self.env["product.uom.factor"]._fields["delegate_uom_id"]
        was_present = field in registry.not_null_fields
        registry.not_null_fields.discard(field)
        if was_present:
            self.addCleanup(registry.not_null_fields.add, field)

        self.env.cr.execute(
            "ALTER TABLE product_uom_factor ALTER COLUMN delegate_uom_id "
            "DROP NOT NULL"
        )
        product = self.env["product.product"].create(
            {"name": name, "uom_id": self.uom_gram.id}
        )
        factor = self.env["product.uom.factor"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "foreign_uom_id": self.uom_ml.id,
                "factor": 0.9,
            }
        )
        self.env.cr.execute(
            "UPDATE product_uom_factor SET delegate_uom_id = NULL WHERE id = %s",
            (factor.id,),
        )
        factor.invalidate_recordset(["delegate_uom_id"])
        return factor

    def test_backfill_creates_delegate_and_sets_id(self):
        """migrate() must create a delegate uom.uom and set delegate_uom_id,
        with relative_uom_id/relative_factor matching the product's base
        UoM and the row's factor.
        """
        factor = self._create_factor_with_null_delegate()
        self.assertFalse(
            factor.delegate_uom_id, "precondition: delegate_uom_id must be NULL"
        )

        self.migrate(self.env.cr, "19.0.4.0.0")
        factor.invalidate_recordset()

        self.assertTrue(
            factor.delegate_uom_id, "delegate_uom_id should be backfilled"
        )
        self.assertEqual(factor.delegate_uom_id.relative_uom_id, self.uom_gram)
        self.assertEqual(factor.delegate_uom_id.relative_factor, 0.9)
        self.assertEqual(factor.delegate_uom_id.name, self.uom_ml.name)

    def test_backfill_idempotent(self):
        """Running migrate() twice must not create a second delegate or
        change the row after the first run already backfilled it.
        """
        factor = self._create_factor_with_null_delegate()

        self.migrate(self.env.cr, "19.0.4.0.0")
        factor.invalidate_recordset()
        first_delegate_id = factor.delegate_uom_id.id
        self.assertTrue(first_delegate_id)

        self.migrate(self.env.cr, "19.0.4.0.0")
        factor.invalidate_recordset()

        self.assertEqual(
            factor.delegate_uom_id.id,
            first_delegate_id,
            "second migrate() run must not create a new delegate",
        )

    def test_no_residual_nulls_after_backfill(self):
        """After migrate(), no product.uom.factor row should have an
        empty delegate_uom_id.

        Verified via raw SQL COUNT rather than an ORM search: an ORM
        search on this model with a domain that doesn't reference
        'active' is itself subject to the same implicit active-record
        filter bug described in the module docstring (it would silently
        report zero matches regardless of whether NULLs remain), which
        would make this assertion a false pass.
        """
        self._create_factor_with_null_delegate("Test Ink - Migration A")
        self._create_factor_with_null_delegate("Test Ink - Migration B")

        self.migrate(self.env.cr, "19.0.4.0.0")

        self.env.cr.execute(
            "SELECT count(*) FROM product_uom_factor "
            "WHERE delegate_uom_id IS NULL"
        )
        (null_count,) = self.env.cr.fetchone()
        self.assertEqual(
            null_count,
            0,
            "no product.uom.factor rows should have a NULL delegate_uom_id "
            "after the migration runs",
        )
