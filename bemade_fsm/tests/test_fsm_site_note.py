"""Site note: a "don't forget this next time" note kept on the service site.

Acceptance criteria
-------------------
1. A note written on a site (res.partner) shows on every FSM task at that site,
   top-level tasks and their subtasks alike (``project.task.fsm_site_note``).
2. Clearing the note removes it from every task at that site.
3. A note on another site does not show on this site's tasks.
4. Changing the note is tracked in the site's chatter.
5. Clicking "Mark as done" from the task form (context key
   ``fsm_site_note_prompt``) on a single top-level FSM task with a partner
   opens the close-out wizard instead of closing the task.
6. "Save & close" in the wizard writes the note to the site (tracked) and
   marks the task done; clearing the text clears the note.
7. "Skip" marks the task done and leaves the note untouched.
8. When a timer is running, the wizard chains into the core
   "stop running timers" wizard instead of closing the task.
9. Programmatic calls (no context key, several tasks at once, subtasks) never
   prompt.
"""

from odoo.tests import Form, tagged

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class TestFsmSiteNote(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("industry_fsm.fsm_project")
        cls.customer = cls._generate_partner(name="Synthetic Customer")
        cls.site = cls._generate_partner(
            name="Receiving dock",
            company_type="person",
            parent=cls.customer,
            location_type="delivery",
        )
        cls.other_site = cls._generate_partner(name="Other Site Co")
        cls.task = cls._make_task("Service visit", cls.site)
        cls.subtask = cls.env["project.task"].create(
            {
                "name": "Inspect pump",
                "project_id": cls.project.id,
                "parent_id": cls.task.id,
            }
        )
        cls.other_task = cls._make_task("Other visit", cls.other_site)

    @classmethod
    def _make_task(cls, name, partner):
        return cls.env["project.task"].create(
            {
                "name": name,
                "project_id": cls.project.id,
                "partner_id": partner.id,
            }
        )

    # -- 1-4: field ----------------------------------------------------------

    def test_note_shows_on_task_and_subtask(self):
        self.site.fsm_site_note = "Gate code changed\nBring the tall ladder"
        self.assertEqual(self.subtask.partner_id, self.site)
        self.assertEqual(self.task.fsm_site_note, "Gate code changed\nBring the tall ladder")
        self.assertEqual(self.subtask.fsm_site_note, "Gate code changed\nBring the tall ladder")

    def test_new_task_at_site_shows_note(self):
        self.site.fsm_site_note = "Park at the back"
        new_task = self._make_task("Next visit", self.site)
        self.assertEqual(new_task.fsm_site_note, "Park at the back")

    def test_clearing_note_removes_it_everywhere(self):
        self.site.fsm_site_note = "Temporary"
        self.site.fsm_site_note = False
        self.assertFalse(self.task.fsm_site_note)
        self.assertFalse(self.subtask.fsm_site_note)

    def test_note_on_other_site_not_shown(self):
        self.other_site.fsm_site_note = "Only for the other site"
        self.assertFalse(self.task.fsm_site_note)
        self.assertEqual(self.other_task.fsm_site_note, "Only for the other site")

    def test_note_change_is_tracked(self):
        self.env.cr.precommit.run()  # flush pending create bookkeeping
        self.site.fsm_site_note = "Tracked note"
        self.env.flush_all()
        self.env.cr.precommit.run()
        tracking = self.env["mail.tracking.value"].search(
            [
                ("mail_message_id.model", "=", "res.partner"),
                ("mail_message_id.res_id", "=", self.site.id),
                ("field_id.name", "=", "fsm_site_note"),
            ]
        )
        self.assertTrue(tracking)

    # -- 5-9: close-out wizard -------------------------------------------------

    def _mark_done_from_form(self, task):
        return task.with_context(fsm_site_note_prompt=True).action_fsm_validate()

    def test_mark_done_from_form_opens_wizard(self):
        self.site.fsm_site_note = "Current note"
        action = self._mark_done_from_form(self.task)
        self.assertIsInstance(action, dict)
        self.assertEqual(action["res_model"], "fsm.site.note.wizard")
        self.assertFalse(self.task.fsm_done)
        wizard = self.env["fsm.site.note.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.task_id, self.task)
        self.assertEqual(wizard.note, "Current note")
        # the wizard's own buttons must not prompt again
        self.assertFalse(action["context"].get("fsm_site_note_prompt"))

    def test_wizard_save_writes_note_and_marks_done(self):
        action = self._mark_done_from_form(self.task)
        with Form(self.env["fsm.site.note.wizard"].browse(action["res_id"])) as wiz_form:
            wiz_form.note = "Remember the spare filter"
        wizard = wiz_form.record
        wizard.action_save()
        self.assertEqual(self.site.fsm_site_note, "Remember the spare filter")
        self.assertTrue(self.task.fsm_done)
        self.assertTrue(self.subtask.fsm_done)

    def test_wizard_save_empty_clears_note(self):
        self.site.fsm_site_note = "Old note"
        action = self._mark_done_from_form(self.task)
        wizard = self.env["fsm.site.note.wizard"].browse(action["res_id"])
        wizard.note = False
        wizard.action_save()
        self.assertFalse(self.site.fsm_site_note)
        self.assertTrue(self.task.fsm_done)

    def test_wizard_skip_leaves_note(self):
        self.site.fsm_site_note = "Keep me"
        action = self._mark_done_from_form(self.task)
        wizard = self.env["fsm.site.note.wizard"].browse(action["res_id"])
        wizard.note = "Changed but skipped"
        wizard.action_skip()
        self.assertEqual(self.site.fsm_site_note, "Keep me")
        self.assertTrue(self.task.fsm_done)

    def test_wizard_chains_into_stop_timers_wizard(self):
        tech = self._generate_project_manager_user("Timer Tech", "fsm_timer_tech")
        self.env["hr.employee"].create({"name": "Timer Tech", "user_id": tech.id})
        timesheet = self.env["account.analytic.line"].with_user(tech).create(
            {"name": "", "project_id": self.project.id}
        )
        timesheet.action_add_time_to_timer(3)
        timesheet.action_change_project_task(self.project.id, self.task.id)
        action = self._mark_done_from_form(self.task)
        wizard = self.env["fsm.site.note.wizard"].browse(action["res_id"])
        wizard.note = "Saved before timers"
        result = wizard.action_save()
        self.assertEqual(self.site.fsm_site_note, "Saved before timers")
        self.assertIsInstance(result, dict)
        self.assertEqual(result["res_model"], "project.task.stop.timers.wizard")
        self.assertFalse(self.task.fsm_done)
        # Confirming the timers wizard closes the task without a new prompt.
        timers_wizard = self.env["project.task.stop.timers.wizard"].browse(result["res_id"])
        timers_wizard.with_context(fsm_site_note_prompt=True).action_confirm()
        self.assertTrue(self.task.fsm_done)

    def test_no_prompt_without_context_key(self):
        self.assertTrue(self.task.action_fsm_validate())
        self.assertTrue(self.task.fsm_done)

    def test_no_prompt_for_several_tasks(self):
        tasks = self.task | self.other_task
        res = tasks.with_context(fsm_site_note_prompt=True).action_fsm_validate()
        self.assertTrue(res)
        self.assertTrue(self.task.fsm_done)
        self.assertTrue(self.other_task.fsm_done)

    def test_no_prompt_for_subtask(self):
        res = self._mark_done_from_form(self.subtask)
        self.assertTrue(res)
        self.assertTrue(self.subtask.fsm_done)

    def test_no_prompt_without_partner(self):
        task = self.env["project.task"].create(
            {"name": "No customer", "project_id": self.project.id}
        )
        task.partner_id = False
        self.assertTrue(self._mark_done_from_form(task))
        self.assertTrue(task.fsm_done)

    def test_mark_done_buttons_carry_context_key(self):
        manager = self._generate_project_manager_user("FSM Manager", "fsm_mgr_note")
        arch = self.env["project.task"].with_user(manager).get_view(
            self.env.ref("project.view_task_form2").id, "form"
        )["arch"]
        self.assertEqual(arch.count("fsm_site_note_prompt"), 2)
        self.assertIn("o_fsm_site_note_banner", arch)

    def test_mobile_form_has_banner_and_context_key(self):
        manager = self._generate_project_manager_user("FSM Manager 2", "fsm_mgr_note2")
        arch = self.env["project.task"].with_user(manager).get_view(
            self.env.ref("industry_fsm.project_task_view_mobile_form").id, "form"
        )["arch"]
        self.assertIn("o_fsm_site_note_banner", arch)
        self.assertEqual(arch.count("fsm_site_note_prompt"), 2)

    def test_fsm_kanban_has_site_note_pin(self):
        arch = self.env["project.task"].get_view(
            self.env.ref("industry_fsm.project_task_view_kanban_fsm").id, "kanban"
        )["arch"]
        self.assertIn("o_fsm_site_note_pin", arch)
