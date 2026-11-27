"""Use case 3 — HR launches a campaign.

Acceptance criteria:
- Launching creates one appraisal per selected employee WITH an Odoo user, evaluator =
  the employee's manager, step « self-evaluation », and the active criteria of the
  campaign's scale (catalogue order) frozen on it with their word pictures, in French
  and English. Criteria of another scale and archived criteria are left out.
- Editing the catalogue afterwards never changes a launched appraisal's wording.
- A criterion missing a word picture for a level blocks the launch (HR is told which).
- Employees without a user are listed for HR and get no appraisal.
- The employee gets a to-do (self-evaluation deadline), in their language; Odoo's own
  appraisal e-mails are not sent for campaign appraisals.
- An employee without a manager gets an appraisal flagged « needs evaluator » and
  cannot submit until HR sets one.
- A campaign is launched once.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestCampaign(CampaignCase):
    def test_launch_creates_frozen_appraisals(self):
        other_scale = self.make_scale(3, name="Other scale")
        self.make_catalogue(other_scale, (1,))
        archived = self.criteria[-1]
        archived.active = False
        self.assertEqual(self.campaign.employee_without_user_ids, self.no_user)
        appraisal = self.launch()
        self.assertEqual(self.campaign.state, "running")
        self.assertEqual(len(self.campaign.appraisal_ids), 2)
        self.assertNotIn(self.no_user, self.campaign.appraisal_ids.employee_id)
        self.assertEqual(appraisal.manager_ids, self.manager)
        self.assertEqual(appraisal.campaign_step, "self_eval")
        self.assertEqual(appraisal.state, "1_new")
        lines = appraisal.campaign_line_ids
        self.assertEqual(lines.criterion_id, self.criteria - archived)
        self.assertEqual(lines.mapped("name"), (self.criteria - archived).mapped("name"))
        first = lines[0]
        self.assertEqual(first.level_text_ids.mapped("value"), [1, 2, 3, 4, 5])
        top = first.level_text_ids[-1]
        self.assertEqual(top.with_context(lang="fr_FR").description, "Portrait FR 1.1 niveau 5")
        self.assertEqual(top.with_context(lang="en_US").description, "EN picture 1.1 level 5")
        self.assertEqual(first.with_context(lang="fr_FR").name, "Critère 1.1")
        # the widget's data, in the reader's language
        data = first.with_context(lang="fr_FR").levels_data
        self.assertEqual([d["value"] for d in data], [1, 2, 3, 4, 5])
        self.assertEqual(data[-1]["name"], "Très haut")
        self.assertEqual(data[-1]["text"], "Portrait FR 1.1 niveau 5")
        self.assertEqual(data[0]["color"], "danger")
        # catalogue edits do not reach launched appraisals
        self.criteria[0].level_ids[-1].with_context(lang="en_US").description = "Changed next year"
        self.criteria[0].with_context(lang="fr_FR").name = "Renommé"
        first.invalidate_recordset()
        top.invalidate_recordset()
        self.assertEqual(top.with_context(lang="en_US").description, "EN picture 1.1 level 5")
        self.assertEqual(first.with_context(lang="fr_FR").name, "Critère 1.1")

    def test_missing_word_picture_blocks_launch(self):
        self.criteria[1].level_ids[2].with_context(lang="en_US").description = False
        with self.assertRaisesRegex(UserError, "Criterion 1.2"):
            self.campaign.with_user(self.hr_user).action_launch()

    def test_employee_todo_and_no_odoo_mail(self):
        appraisal = self.launch()
        todo = appraisal.activity_ids.filtered(lambda a: a.user_id == self.employee_user)
        self.assertEqual(len(todo), 1)
        self.assertEqual(str(todo.date_deadline), "2026-12-01")
        # in the employee's language (French); through the wording hook, which a company
        # module may override (e.g. several languages)
        Campaign = self.env["hr.appraisal.campaign"]
        self.assertIn("Complétez votre auto-évaluation", todo.summary)
        self.assertEqual(todo.summary, Campaign._campaign_render_text(
            lambda env: env._("Complete your self-evaluation"), self.employee_user))
        colleague_todo = (self.campaign.appraisal_ids - appraisal).activity_ids
        self.assertIn("Complete your self-evaluation", colleague_todo.summary)
        self.assertEqual(colleague_todo.summary, Campaign._campaign_render_text(
            lambda env: env._("Complete your self-evaluation"), self.colleague_user))
        self.set_self(appraisal, [3] * self.n_criteria)
        mails = self.env["mail.mail"].sudo().search_count([("subject", "ilike", "appraisal")])
        appraisal.with_user(self.employee_user).action_campaign_submit_self()
        self.assertEqual(appraisal.state, "2_pending")
        self.assertEqual(
            self.env["mail.mail"].sudo().search_count([("subject", "ilike", "appraisal")]), mails)

    def test_launch_twice_refused(self):
        self.launch()
        with self.assertRaises(UserError):
            self.campaign.with_user(self.hr_user).action_launch()

    def test_employee_without_manager_needs_evaluator(self):
        self.employee.parent_id = False
        appraisal = self.launch()
        self.assertTrue(appraisal.campaign_needs_evaluator)
        self.set_self(appraisal, [3] * self.n_criteria)
        with self.assertRaises(UserError):
            appraisal.with_user(self.employee_user).action_campaign_submit_self()
        appraisal.with_user(self.hr_user).manager_ids = self.director
        appraisal.with_user(self.employee_user).action_campaign_submit_self()
        self.assertEqual(appraisal.campaign_step, "manager_eval")

    def test_campaign_evaluations_grouped_by_step(self):
        self.launch()
        action = self.campaign.with_user(self.hr_user).action_open_appraisals()
        self.assertEqual(action["context"].get("search_default_group_campaign_step"), 1)
        self.assertEqual(action["context"].get("default_campaign_id"), self.campaign.id)

    def test_creation_note(self):
        self.assertIn("Evaluation campaign created", str(self.campaign.message_ids[-1].body))
