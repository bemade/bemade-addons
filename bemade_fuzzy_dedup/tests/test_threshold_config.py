"""Acceptance criteria: the similarity threshold.

The single knob. Its failure mode is asymmetric: a threshold read as 0.0 makes
the ``%`` operator match every pair in the table, so a malformed value must
never be read as zero.

1.  With no parameter set, the documented default applies.
2.  A valid value in (0, 1] is used.
3.  A non-numeric value falls back to the default and warns.
4.  A value of 0, a negative value, or a value above 1 falls back to the
    default and warns.
5.  Raising the threshold narrows what a scan proposes; lowering it widens it.
"""

from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models.dedup_target import DEFAULT_THRESHOLD
from .common import FuzzyDedupCase

PARAM = "bemade_fuzzy_dedup.similarity_threshold"


@tagged("post_install", "-at_install")
class TestThresholdConfig(FuzzyDedupCase):
    def setUp(self):
        super().setUp()
        self.Param = self.env["ir.config_parameter"].sudo()
        self.default = DEFAULT_THRESHOLD

    def test_01_default_when_unset(self):
        self.Param.search([("key", "=", PARAM)]).unlink()
        self.assertEqual(self._target()._similarity_threshold(), self.default)

    def test_02_valid_value_used(self):
        self.Param.set_param(PARAM, "0.8")
        self.assertEqual(self._target()._similarity_threshold(), 0.8)

    @mute_logger("odoo.addons.bemade_fuzzy_dedup.models.dedup_target")
    def test_03_non_numeric_falls_back(self):
        self.Param.set_param(PARAM, "loose-ish")
        self.assertEqual(self._target()._similarity_threshold(), self.default)

    @mute_logger("odoo.addons.bemade_fuzzy_dedup.models.dedup_target")
    def test_04_out_of_range_falls_back(self):
        target = self._target()
        for raw in ("0", "0.0", "-0.5", "1.5"):
            with self.subTest(raw=raw):
                self.Param.set_param(PARAM, raw)
                self.assertEqual(
                    target._similarity_threshold(),
                    self.default,
                    "a threshold of zero would match every pair in the table",
                )

    def test_05_threshold_widens_and_narrows_the_scan(self):
        a = self._partner("Northwind Trading Company")
        b = self._partner("Northwind Trading Compny")
        pair = frozenset((a.id, b.id))
        target = self._target()
        self.Param.set_param(PARAM, "0.99")
        self.assertNotIn(pair, self._pairs(target))
        self.Param.set_param(PARAM, "0.2")
        self.assertIn(pair, self._pairs(target))
