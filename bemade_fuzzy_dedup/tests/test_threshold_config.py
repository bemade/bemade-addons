"""Acceptance criteria: the similarity threshold.

Set per target and editable on its form, because what counts as similar
differs by model: a value that finds real duplicate contacts will happily
propose three siblings who share a surname.

Its failure mode is asymmetric. A threshold read as 0.0 makes the ``%``
operator match every pair in the table, so no path may ever yield zero.

1.  A new target defaults to the instance-wide config parameter.
2.  With no parameter set, the documented default applies.
3.  A target's own threshold is what its scan uses.
4.  Two targets can hold different thresholds.
5.  A value outside (0, 1] is rejected on write, rather than silently
    matching everything.
6.  A malformed or out-of-range CONFIG parameter falls back to the default
    and warns, since it is only a default and cannot be validated on entry.
7.  Raising a target's threshold narrows what its scan proposes; lowering it
    widens it.
"""

from odoo.exceptions import ValidationError
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

    def test_01_new_target_defaults_to_the_config_parameter(self):
        self.Param.set_param(PARAM, "0.8")
        self.assertAlmostEqual(self._target().similarity_threshold, 0.8, places=2)

    def test_02_documented_default_when_parameter_unset(self):
        self.Param.search([("key", "=", PARAM)]).unlink()
        self.assertAlmostEqual(
            self._target().similarity_threshold, self.default, places=2
        )

    def test_03_the_targets_own_threshold_is_used(self):
        target = self._target()
        target.similarity_threshold = 0.42
        self.assertAlmostEqual(target._similarity_threshold(), 0.42, places=2)

    def test_04_targets_can_differ(self):
        partners = self._target()
        countries = self.Target.create(
            {
                "model_id": self.env["ir.model"]._get_id("res.country"),
                "field_id": self.env["ir.model.fields"]._get("res.country", "name").id,
            }
        )
        partners.similarity_threshold = 0.9
        countries.similarity_threshold = 0.3
        self.assertAlmostEqual(partners._similarity_threshold(), 0.9, places=2)
        self.assertAlmostEqual(countries._similarity_threshold(), 0.3, places=2)

    def test_05_out_of_range_is_rejected_on_write(self):
        target = self._target()
        for bad in (0, -0.5, 1.5):
            with self.subTest(bad=bad):
                with self.assertRaises(
                    ValidationError,
                    msg="a threshold of zero would match every pair in the table",
                ):
                    target.similarity_threshold = bad

    @mute_logger("odoo.addons.bemade_fuzzy_dedup.models.dedup_target")
    def test_06_bad_config_parameter_falls_back(self):
        target = self._target()
        for raw in ("loose-ish", "0", "-0.5", "1.5"):
            with self.subTest(raw=raw):
                self.Param.set_param(PARAM, raw)
                self.assertAlmostEqual(
                    target._global_similarity_threshold(), self.default, places=2
                )

    def test_07_threshold_widens_and_narrows_the_scan(self):
        a = self._partner("Northwind Trading Company")
        b = self._partner("Northwind Trading Compny")
        pair = frozenset((a.id, b.id))
        target = self._target()
        target.similarity_threshold = 0.99
        self.assertNotIn(pair, self._pairs(target))
        target.similarity_threshold = 0.2
        self.assertIn(pair, self._pairs(target))
