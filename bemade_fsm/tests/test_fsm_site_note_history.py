"""Site note: technicians update it from a visit, every change is kept (task 1727).

Acceptance criteria
-------------------
1. A Field Service user who cannot edit contacts can update the site note
   from any FSM task at that site with the « Update site note » button
   (``action_open_fsm_site_note_edit`` -> ``fsm.site.note.edit.wizard``):
   the site's note changes, a history row records the editor, the date and
   the visit, and a bilingual note (French first) is posted on the visit.
2. The same window clears the note when emptied.
3. The button write path is limited: it refuses a task that is not a field
   service task and a task the user cannot read, and it only ever writes the
   site note (no other partner field).
4. Every real change of the site note creates exactly one history row,
   whatever the path: the contact form (partner write), a partner created
   with a note, the close-out wizard (which also posts on the visit) and the
   new button. Saving the same text again creates nothing.
5. The history is read-only: a technician (or a manager) can read it but can
   neither create, edit nor delete rows.
6. The upgrade seed creates one history row per site with a non-empty note
   (dated at the partner's last write, credited to OdooBot when the last
   writer of the note is not known) and is idempotent.
7. « Mark as Delivered » stays manager-only: the task form shows no
   ``action_fsm_validate`` button to a technician, both buttons to a
   Field Service manager.
"""

from odoo.exceptions import AccessError, UserError
from odoo.tests import Form, tagged
from odoo.tools.misc import mute_logger

from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class TestFsmSiteNoteHistory(BemadeFSMBaseTest):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("industry_fsm.fsm_project")
        cls.site = cls._generate_partner(name="Synthetic Site Co")
        cls.task = cls.env["project.task"].create(
            {
                "name": "Service visit",
                "project_id": cls.project.id,
                "partner_id": cls.site.id,
            }
        )
        cls.tech = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Synthetic Technician",
                    "login": "fsm_synthetic_tech",
                    "email": "tech@example.com",
                    "group_ids": [
                        (
                            6,
                            0,
                            [
                                cls.env.ref("base.group_user").id,
                                cls.env.ref("project.group_project_user").id,
                                cls.env.ref("industry_fsm.group_fsm_user").id,
                            ],
                        )
                    ],
                }
            )
        )
        cls.manager = cls._generate_project_manager_user(
            "Synthetic FSM Manager", "fsm_synthetic_manager"
        )
        cls.History = cls.env["fsm.site.note.history"]

    def _history(self, partner=None):
        return self.History.search([("partner_id", "=", (partner or self.site).id)])

    def _update_from_visit(self, note, user=None, task=None):
        task = (task or self.task).with_user(user or self.tech)
        action = task.action_open_fsm_site_note_edit()
        self.assertEqual(action["res_model"], "fsm.site.note.edit.wizard")
        self.assertEqual(action["target"], "new")
        wizard = (
            self.env["fsm.site.note.edit.wizard"]
            .with_user(user or self.tech)
            .browse(action["res_id"])
        )
        with Form(wizard) as wiz_form:
            wiz_form.note = note
        return wiz_form.record.action_save()

    # -- 1-3: the « Update site note » button ---------------------------------

    def test_technician_cannot_edit_contacts(self):
        """Premise: the technician has no write right on contacts."""
        with mute_logger("odoo.addons.base.models.ir_model"), self.assertRaises(
            AccessError
        ):
            self.site.with_user(self.tech).write({"fsm_site_note": "Nope"})

    def test_technician_updates_note_from_visit(self):
        self.site.fsm_site_note = "Old note"
        action = self.task.with_user(self.tech).action_open_fsm_site_note_edit()
        wizard = self.env["fsm.site.note.edit.wizard"].browse(action["res_id"])
        self.assertEqual(wizard.note, "Old note", "the window opens on the current note")
        self._update_from_visit("Gate code changed")
        self.assertEqual(self.site.fsm_site_note, "Gate code changed")
        self.assertEqual(self.task.fsm_site_note, "Gate code changed")
        newest = self._history()[0]
        self.assertEqual(newest.content, "Gate code changed")
        self.assertEqual(newest.author_id, self.tech)
        self.assertEqual(newest.task_id, self.task)
        self.assertTrue(newest.note_datetime)
        messages = self.task.message_ids.filtered(
            lambda m: "Note du site mise à jour / Site note updated" in (m.body or "")
        )
        self.assertEqual(len(messages), 1)
        self.assertIn("Gate code changed", messages.body)
        self.assertEqual(messages.author_id, self.tech.partner_id)
        self.assertTrue(messages.body.index("Note du site") < messages.body.index("Site note"))

    def test_technician_clears_note_from_visit(self):
        self.site.fsm_site_note = "Temporary"
        self._update_from_visit(False)
        self.assertFalse(self.site.fsm_site_note)
        newest = self._history()[0]
        self.assertFalse(newest.content)
        self.assertEqual(newest.author_id, self.tech)
        self.assertTrue(
            self.task.message_ids.filtered(
                lambda m: "Note du site effacée / Site note cleared" in (m.body or "")
            )
        )

    def test_unchanged_note_from_visit_logs_nothing(self):
        self.site.fsm_site_note = "Same text"
        before = len(self._history())
        messages_before = len(self.task.message_ids)
        self._update_from_visit("Same text")
        self.assertEqual(len(self._history()), before)
        self.assertEqual(len(self.task.message_ids), messages_before)

    def test_button_refuses_non_fsm_task(self):
        other_project = self.env["project.project"].create({"name": "Not FSM"})
        task = self.env["project.task"].create(
            {
                "name": "Office task",
                "project_id": other_project.id,
                "partner_id": self.site.id,
            }
        )
        wizard = self.env["fsm.site.note.edit.wizard"].create(
            {"task_id": task.id, "note": "Should not land"}
        )
        with self.assertRaises(UserError):
            wizard.with_user(self.manager).action_save()
        self.assertFalse(self.site.fsm_site_note)

    def test_button_refuses_unreadable_task(self):
        private_project = self.env["project.project"].create(
            {
                "name": "Private FSM",
                "is_fsm": True,
                "privacy_visibility": "followers",
                "company_id": self.env.company.id,
            }
        )
        task = self.env["project.task"].create(
            {
                "name": "Hidden visit",
                "project_id": private_project.id,
                "partner_id": self.site.id,
            }
        )
        with self.assertRaises(AccessError):
            task.with_user(self.tech).check_access("read")
        wizard = self.env["fsm.site.note.edit.wizard"].create(
            {"task_id": task.id, "note": "Should not land"}
        )
        with mute_logger("odoo.addons.base.models.ir_rule"), self.assertRaises(
            AccessError
        ):
            wizard.with_user(self.tech).action_save()
        self.assertFalse(self.site.fsm_site_note)

    def test_button_writes_only_the_site_note(self):
        self.site.write({"name": "Synthetic Site Co", "comment": False})
        self._update_from_visit("Only the note")
        self.assertEqual(self.site.name, "Synthetic Site Co")
        self.assertFalse(self.site.comment)
        self.assertEqual(self.site.fsm_site_note, "Only the note")

    # -- 4: every path logs exactly once ----------------------------------------

    def test_partner_form_edit_creates_history(self):
        # A plain write as the contact-form save does: a Form on res.partner
        # would load every sibling addon's partner view in the CI build.
        self.site.with_user(self.manager).write(
            {"fsm_site_note": "Written on the contact"}
        )
        rows = self._history()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, "Written on the contact")
        self.assertEqual(rows.author_id, self.manager)
        self.assertFalse(rows.task_id)

    def test_partner_created_with_note_creates_history(self):
        partner = self.env["res.partner"].create(
            {"name": "New Synthetic Site", "fsm_site_note": "From day one"}
        )
        rows = self._history(partner)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.content, "From day one")
        self.assertFalse(
            self._history(self.env["res.partner"].create({"name": "No note site"}))
        )

    def test_noop_partner_write_creates_nothing(self):
        self.site.fsm_site_note = "Stable"
        self.assertEqual(len(self._history()), 1)
        self.site.write({"fsm_site_note": "Stable"})
        self.site.write({"fsm_site_note": "Stable", "comment": "unrelated"})
        self.assertEqual(len(self._history()), 1)
        # empty string and False are the same "no note"
        self.site.fsm_site_note = False
        self.site.fsm_site_note = ""
        self.assertEqual(len(self._history()), 2)

    def test_history_is_newest_first(self):
        self.site.fsm_site_note = "First"
        self.site.fsm_site_note = "Second"
        self.assertEqual(self._history().mapped("content"), ["Second", "First"])

    def test_closeout_wizard_creates_history_and_posts(self):
        task = self.task.with_user(self.manager)
        action = task.with_context(fsm_site_note_prompt=True).action_fsm_validate()
        wizard = self.env["fsm.site.note.wizard"].with_user(self.manager).browse(
            action["res_id"]
        )
        with Form(wizard) as wiz_form:
            wiz_form.note = "Bring the spare filter"
        wiz_form.record.action_save()
        self.assertEqual(self.site.fsm_site_note, "Bring the spare filter")
        rows = self._history()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.author_id, self.manager)
        self.assertEqual(rows.task_id, self.task)
        self.assertTrue(
            self.task.message_ids.filtered(
                lambda m: "Note du site mise à jour / Site note updated" in (m.body or "")
            )
        )
        self.assertTrue(self.task.fsm_done)

    # -- 5: read-only history ----------------------------------------------------

    def test_history_read_only_for_everyone(self):
        self.site.fsm_site_note = "Audited"
        row = self._history()
        for user in (self.tech, self.manager):
            self.assertEqual(row.with_user(user).content, "Audited")
            self.assertEqual(
                self.site.with_user(user).fsm_site_note_history_ids, row
            )
            with mute_logger("odoo.addons.base.models.ir_model"):
                with self.assertRaises(AccessError):
                    self.History.with_user(user).create(
                        {"partner_id": self.site.id, "content": "Forged"}
                    )
                with self.assertRaises(AccessError):
                    row.with_user(user).write({"content": "Rewritten"})
                with self.assertRaises(AccessError):
                    row.with_user(user).unlink()
        self.assertEqual(row.content, "Audited")

    # -- 6: upgrade seed ----------------------------------------------------------

    def test_seed_from_current_notes(self):
        self.site.fsm_site_note = "Pre-existing"
        other = self._generate_partner(name="Other Synthetic Site")
        other.fsm_site_note = "Also pre-existing"
        self.History.sudo().search([]).unlink()
        self.env.flush_all()
        created = self.History._seed_from_current_notes()
        self.assertGreaterEqual(created, 2)
        row = self._history()
        self.assertEqual(len(row), 1)
        self.assertEqual(row.content, "Pre-existing")
        self.assertEqual(row.note_datetime, self.site.write_date)
        self.assertEqual(row.author_id, self.env.ref("base.user_root"))
        self.assertEqual(len(self._history(other)), 1)
        # idempotent: a second run adds nothing
        self.assertEqual(self.History._seed_from_current_notes(), 0)
        self.assertEqual(len(self._history()), 1)

    # -- 7: Mark as Delivered stays manager-only -------------------------------

    def _form_buttons(self, user, name):
        arch = (
            self.env["project.task"]
            .with_user(user)
            .get_view(self.env.ref("project.view_task_form2").id, "form")["arch"]
        )
        return arch.count(f'name="{name}"')

    def test_mark_as_delivered_manager_only(self):
        self.assertEqual(self._form_buttons(self.tech, "action_fsm_validate"), 0)
        self.assertEqual(self._form_buttons(self.manager, "action_fsm_validate"), 2)

    def test_update_button_shown_to_technicians(self):
        self.assertGreaterEqual(
            self._form_buttons(self.tech, "action_open_fsm_site_note_edit"), 2
        )
