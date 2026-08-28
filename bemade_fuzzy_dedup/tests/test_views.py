"""Acceptance criteria: the review screens build and accept input.

View arch is validated at install, which catches malformed arch and bad button
targets. What that does not catch is a form that references a field the model
does not expose, or an inline list that cannot actually be edited -- so the
screens a reviewer uses are exercised through ``Form``.

1.  The target form builds and a target can be created through it.
2.  The group form builds on a real group, exposing its records.
3.  The master can be changed through the group form's inline list, which is
    the whole point of the screen.
"""

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
