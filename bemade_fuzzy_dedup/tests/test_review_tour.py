"""Acceptance criteria: the reviewer flow works in a real browser.

Python cannot cover this. Install-time validation checks arch and button
targets; ``Form`` checks model-level wiring. Neither evaluates client-side
widget options, so the target form once passed every Python test while
raising ``RPC_ERROR 404`` the moment a human opened it.

1.  The target form renders, domain widget included.
2.  Scanning from the form proposes at least one group and lands on it.
3.  The group shows the records it proposes merging.
4.  Merging asks for confirmation and leaves the group in ``merged``. The
    tour proves the click-through works; the resulting state is asserted here
    rather than through statusbar markup, which varies with theme and viewport.
"""

from odoo.tests import HttpCase, tagged

SCOPE = "FZTOUR"


@tagged("post_install", "-at_install")
class TestReviewTour(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env["res.partner"]
        for name, ref in (
            ("Tour Duplicate A", "Ashbourne Millwork"),
            ("Tour Duplicate B", "Ashbourne Millwrk"),
        ):
            Partner.create({"name": name, "function": SCOPE, "ref": ref})
        cls.target = cls.env["bemade.dedup.target"].create(
            {
                "model_id": cls.env["ir.model"]._get_id("res.partner"),
                "field_id": cls.env["ir.model.fields"]._get("res.partner", "ref").id,
                "domain": "[('function', '=', '%s')]" % SCOPE,
            }
        )

    def test_review_tour(self):
        self.start_tour(
            "/odoo/action-bemade_fuzzy_dedup.bemade_dedup_target_action/%s"
            % self.target.id,
            "fuzzy_dedup_review_tour",
            login="admin",
        )
        self.env.invalidate_all()
        groups = self.env["bemade.dedup.group"].search(
            [("target_id", "=", self.target.id)]
        )
        self.assertTrue(groups, "the scan proposed nothing")
        self.assertEqual(
            groups.mapped("state"),
            ["merged"],
            "the tour clicked through the merge, so the group must be merged",
        )
