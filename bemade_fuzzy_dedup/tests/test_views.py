"""Acceptance criteria: the review screens build and accept input.

View arch is validated at install, which catches malformed arch and bad button
targets. What that does not catch is a form that references a field the model
does not expose, or an inline list that cannot actually be edited -- so the
screens a reviewer uses are exercised through ``Form``.

1.  The target form builds and a target can be created through it.
2.  The group form builds on a real group, exposing its records.
3.  The master can be changed through the group form's inline list, which is
    the whole point of the screen.
4.  Targets and groups are named for what they are. Without an explicit
    display name they read as "bemade.dedup.target,1" in breadcrumbs, tooltips,
    relational fields and this module's own log lines.
5.  Every ``widget="domain"`` option naming a model resolves: either to a real
    model, or to a field actually PRESENT in the same view. The widget treats
    the option as an indirection only when a field of that name is among the
    view's loaded fields; otherwise it passes the string through as a model
    name and the screen 404s at runtime. Form() does not evaluate widget
    options, so nothing else here would catch it.
"""

import ast

from lxml import etree

from odoo.tests import Form, tagged

from .common import FuzzyDedupCase


@tagged("post_install", "-at_install")
class TestViews(FuzzyDedupCase):
    def test_01_target_form_builds(self):
        form = Form(self.env["bemade.dedup.target"])
        form.model_id = self.env["ir.model"].search([("model", "=", "res.partner")])
        form.field_id = self.env["ir.model.fields"]._get("res.partner", "ref")
        target = form.save()
        self.assertEqual(target.model_name, "res.partner")

    def test_02_group_form_builds(self):
        self._partner("Marlow Castings")
        self._partner("Marlow Castngs")
        group = self._target()._scan()
        form = Form(group)
        self.assertEqual(len(form.record_ids), 2)

    def test_03_master_can_be_changed_from_the_form(self):
        first = self._partner("Ashford Bearings")
        second = self._partner("Ashford Bearngs")
        group = self._target()._scan()
        self.assertEqual(group.record_ids.filtered("is_master").res_id, first.id)
        with Form(group) as form:
            for index in range(len(form.record_ids)):
                with form.record_ids.edit(index) as line:
                    line.is_master = line.res_id == second.id
        self.assertEqual(group.record_ids.filtered("is_master").res_id, second.id)

    def test_04_domain_widget_model_options_resolve(self):
        views = self.env["ir.ui.view"].search(
            [
                (
                    "model",
                    "in",
                    (
                        "bemade.dedup.target",
                        "bemade.dedup.group",
                        "bemade.dedup.group.record",
                    ),
                )
            ]
        )
        self.assertTrue(views, "no views found to check")
        for view in views:
            arch = etree.fromstring(view.arch)
            present = {node.get("name") for node in arch.iter("field")}
            for node in arch.iter("field"):
                if node.get("widget") != "domain":
                    continue
                options = ast.literal_eval(node.get("options") or "{}")
                model_option = options.get("model")
                if not model_option:
                    continue
                with self.subTest(view=view.name, field=node.get("name")):
                    self.assertTrue(
                        model_option in self.env or model_option in present,
                        "domain widget on %s references %r, which is neither a "
                        "model nor a field present in this view; the widget "
                        "would pass it through as a model name and 404"
                        % (node.get("name"), model_option),
                    )

    def test_05_groups_are_named_for_the_records_they_hold(self):
        """A group's name is the duplicates it proposes.

        "res.partner (2 records)" is true of every group and tells a reviewer
        nothing; the names are the only thing that distinguishes one row of
        the review queue from another.
        """
        target = self._target()
        self.assertEqual(target.display_name, "res.partner / ref")
        first = self._partner("Wrenfield Tooling")
        second = self._partner("Wrenfield Toolng")
        group = target._scan()
        self.assertIn(first.display_name, group.display_name)
        self.assertIn(second.display_name, group.display_name)
        self.assertNotIn("bemade.dedup", group.display_name)

    def test_06_review_columns_carry_the_decision(self):
        """What a reviewer needs on screen: the matched value, and a link out.

        Deciding whether two records are the same thing means seeing what they
        matched on and being able to open them; neither is inferable from the
        group row alone.
        """
        first = self._partner("Halberd Castings")
        self._partner("Halberd Castngs")
        group = self._target()._scan()
        line = group.record_ids.filtered(lambda r: r.res_id == first.id)
        self.assertEqual(line.compared_value, first.ref)
        self.assertEqual(line.record_ref, first)

    def test_07_similarity_is_the_weakest_link(self):
        """A cluster is only as trustworthy as its least similar pair.

        Chaining A~B~C can join two good matches into one bad group, so the
        score shown is the minimum within the cluster rather than the average.
        """
        target = self._target()
        self._partner("Ravensworth Engineering")
        self._partner("Ravensworth Engineerng")
        group = target._scan()
        self.assertGreater(group.similarity, 0.0)
        self.assertLessEqual(group.similarity, 1.0)
        pairs = target._candidate_pairs_scored()
        within = [score for _a, _b, score in pairs]
        # The field stores two decimals on purpose — a reviewer reads a
        # percentage, not a float.
        self.assertAlmostEqual(group.similarity, min(within), places=2)
