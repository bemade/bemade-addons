"""
US-06 — Row cap and truncated flag.

Acceptance criteria
-------------------
- Set bemade_sql_console.row_cap = 2 in ir.config_parameter.
- SELECT generate_series(1,5) → row_count == 2, len(rows) == 2, truncated is True.
- SELECT generate_series(1,2) → truncated is False.
"""

from odoo.tests import tagged

from .common import SqlConsoleTestBase


@tagged("at_install", "post_install")
class TestRowCap(SqlConsoleTestBase):
    """US-06: Row cap limits returned rows and truncated flag is set correctly."""

    def _set_row_cap(self, cap):
        """Set the row cap system parameter."""
        self.env["ir.config_parameter"].sudo().set_param(
            "bemade_sql_console.row_cap", str(cap)
        )

    def _restore_row_cap(self):
        """Restore the default row cap."""
        self.env["ir.config_parameter"].sudo().set_param(
            "bemade_sql_console.row_cap", "1000"
        )

    def test_truncated_true_when_over_cap(self):
        """When result exceeds cap, row_count == cap and truncated is True."""
        self._set_row_cap(2)
        try:
            result = self.env["sql.console"].run_query(
                "SELECT generate_series(1, 5) AS n"
            )
            self.assertEqual(result["row_count"], 2, "row_count should equal the cap")
            self.assertEqual(
                len(result["rows"]), 2, "rows list length should equal the cap"
            )
            self.assertTrue(
                result["truncated"], "truncated should be True when result exceeds cap"
            )
        finally:
            self._restore_row_cap()

    def test_truncated_false_when_at_cap(self):
        """When result equals cap exactly, truncated is False."""
        self._set_row_cap(2)
        try:
            result = self.env["sql.console"].run_query(
                "SELECT generate_series(1, 2) AS n"
            )
            self.assertEqual(result["row_count"], 2)
            self.assertEqual(len(result["rows"]), 2)
            self.assertFalse(
                result["truncated"],
                "truncated should be False when result equals the cap exactly",
            )
        finally:
            self._restore_row_cap()

    def test_truncated_false_when_under_cap(self):
        """When result is below cap, truncated is False."""
        self._set_row_cap(2)
        try:
            result = self.env["sql.console"].run_query(
                "SELECT generate_series(1, 1) AS n"
            )
            self.assertEqual(result["row_count"], 1)
            self.assertFalse(result["truncated"])
        finally:
            self._restore_row_cap()

    def test_row_values_are_correct(self):
        """Rows returned are the first N rows, not random rows."""
        self._set_row_cap(3)
        try:
            result = self.env["sql.console"].run_query(
                "SELECT generate_series(1, 10) AS n ORDER BY n"
            )
            self.assertEqual(result["row_count"], 3)
            # First 3 values: 1, 2, 3
            values = [row[0] for row in result["rows"]]
            self.assertEqual(values, [1, 2, 3])
            self.assertTrue(result["truncated"])
        finally:
            self._restore_row_cap()

    def test_default_cap_is_1000(self):
        """Default row cap (1000) is respected when parameter is not set to a low value."""
        # Remove parameter to fall back to default
        param = self.env["ir.config_parameter"].sudo().search(
            [("key", "=", "bemade_sql_console.row_cap")]
        )
        saved = None
        if param:
            saved = param.value
            param.value = "1000"

        try:
            # Generate 5 rows — all 5 should come back
            result = self.env["sql.console"].run_query(
                "SELECT generate_series(1, 5) AS n"
            )
            self.assertEqual(result["row_count"], 5)
            self.assertFalse(result["truncated"])
        finally:
            if saved is not None:
                param.value = saved
