"""Use case 1 — HR configures the rating scale, the sections and the criteria.

Acceptance criteria:
- A scale has any number of levels (tested with 3 and 5); each level has a value and a
  name translated in English and French; values are unique within a scale and ≥ 1.
- Each level gets an automatic badge colour from its position (lowest red, highest
  green) unless HR picks one.
- A criterion of a section gets one word-picture line per level of the section's
  scale, automatically; adding a level to the scale adds the line to its criteria.
- Criteria are ordered as the catalogue: section sequence, then criterion sequence.
- HR does all of it from the forms (scale with its levels, section, criterion with its
  word pictures, campaign whose scale fills in the thresholds).
- Sections and the scale carry default thresholds (points) that a new campaign
  copies, with the scale's target score and alignment gap; the campaign then keeps
  its own copy (editing the defaults does not change a campaign).
"""

from psycopg2 import IntegrityError

from odoo import Command
from odoo.tests import Form, tagged
from odoo.tools.misc import mute_logger

from .common import CampaignCase


@tagged("post_install", "-at_install")
class TestScale(CampaignCase):
    def test_three_and_five_levels_translated(self):
        three = self.make_scale(3)
        self.assertEqual(three.level_ids.mapped("value"), [1, 2, 3])
        self.assertEqual(three.max_value, 3)
        self.assertEqual(self.scale.max_value, 5)
        self.assertEqual(len(self.scale.level_ids), 5)
        top = self.scale.level_ids[-1]
        self.assertEqual(top.with_context(lang="en_US").name, "Very high")
        self.assertEqual(top.with_context(lang="fr_FR").name, "Très haut")

    def test_level_values_unique_and_positive(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.scale.write({"level_ids": [Command.create({"value": 2, "name": "Twice"})]})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.env.cr.savepoint():
            self.scale.write({"level_ids": [Command.create({"value": 0, "name": "Zero"})]})

    def test_badge_colours_by_position(self):
        self.assertEqual(
            self.scale.level_ids.mapped("display_color"),
            ["danger", "warning", "secondary", "info", "success"])
        four = self.make_scale(4)
        self.assertEqual(four.level_ids.mapped("display_color"),
                         ["danger", "warning", "info", "success"])
        four.level_ids[1].color = "primary"
        self.assertEqual(four.level_ids[1].display_color, "primary")

    def test_criterion_gets_one_picture_per_level(self):
        criterion = self.criteria[0]
        self.assertEqual(criterion.level_ids.mapped("value"), [1, 2, 3, 4, 5])
        self.assertEqual(
            criterion.level_ids[-1].with_context(lang="fr_FR").description,
            "Portrait FR 1.1 niveau 5")
        self.scale.write({"level_ids": [Command.create({"value": 6, "name": "Outstanding"})]})
        self.assertEqual(criterion.level_ids.mapped("value"), [1, 2, 3, 4, 5, 6])

    def test_catalogue_order(self):
        Criterion = self.env["hr.appraisal.campaign.criterion"]
        self.sections[0].sequence = 20  # section 1 now after section 2
        ordered = Criterion.search([("scale_id", "=", self.scale.id)])
        self.assertEqual(
            ordered.mapped("name"),
            ["Criterion 2.1", "Criterion 2.2", "Criterion 2.3", "Criterion 1.1", "Criterion 1.2"])

    def test_campaign_copies_defaults_and_keeps_its_own(self):
        self.set_thresholds(self.scale, None, {5: 22, 4: 18, 3: 12, 2: 8})
        self.set_thresholds(self.sections[0], self.sections[0], {5: 9, 3: 5})
        self.scale.write({"default_target_score": 17, "default_alignment_gap": 2})
        campaign = self.env["hr.appraisal.campaign"].with_user(self.hr_user).create({
            "name": "Copy test", "scale_id": self.scale.id})
        overall = campaign.threshold_ids.filtered(lambda t: not t.section_id)
        self.assertEqual(sorted(overall.mapped("min_score")), [8, 12, 18, 22])
        section = campaign.threshold_ids.filtered(lambda t: t.section_id == self.sections[0])
        self.assertEqual(sorted(section.mapped("min_score")), [5, 9])
        self.assertEqual((campaign.target_score, campaign.alignment_gap), (17, 2))
        # editing the defaults afterwards does not change the campaign
        self.set_thresholds(self.scale, None, {5: 30})
        self.assertEqual(sorted(campaign.threshold_ids.filtered(
            lambda t: not t.section_id).mapped("min_score")), [8, 12, 18, 22])
        # HR can reload the defaults while the campaign is a draft
        campaign.with_user(self.hr_user).action_reset_thresholds()
        self.assertEqual(campaign.threshold_ids.filtered(
            lambda t: not t.section_id).mapped("min_score"), [30])

    def test_configuration_through_the_forms(self):
        Scale = self.env["hr.appraisal.campaign.scale"].with_user(self.hr_user)
        with Form(Scale) as scale_form:
            scale_form.name = "Form scale"
            for value, name in ((1, "Low"), (2, "Mid"), (3, "High")):
                with scale_form.level_ids.new() as level:
                    level.value = value
                    level.name = name
            scale_form.default_target_score = 6
        scale = scale_form.record
        self.assertEqual(scale.level_ids.mapped("name"), ["Low", "Mid", "High"])
        Section = self.env["hr.appraisal.campaign.section"].with_user(self.hr_user)
        with Form(Section) as section_form:
            section_form.name = "Form section"
            section_form.scale_id = scale
            with section_form.threshold_ids.new() as threshold:
                threshold.level_id = scale.level_ids[-1]
                threshold.min_score = 5
        section = section_form.record
        Criterion = self.env["hr.appraisal.campaign.criterion"].with_user(self.hr_user)
        with Form(Criterion) as criterion_form:
            criterion_form.name = "Form criterion"
            criterion_form.section_id = section
        criterion = criterion_form.record
        self.assertEqual(criterion.level_ids.mapped("value"), [1, 2, 3])
        with Form(criterion) as criterion_form:
            for index in range(3):
                with criterion_form.level_ids.edit(index) as picture:
                    picture.description = f"Form picture {index + 1}"
        self.assertFalse(criterion._missing_pictures())
        Campaign = self.env["hr.appraisal.campaign"].with_user(self.hr_user)
        with Form(Campaign) as campaign_form:
            campaign_form.name = "Form campaign"
            campaign_form.scale_id = scale
            self.assertEqual(len(campaign_form.threshold_ids), 1)
            self.assertEqual(campaign_form.target_score, 6)
        campaign = campaign_form.record
        self.assertEqual(
            (campaign.threshold_ids.section_id, campaign.threshold_ids.min_score), (section, 5))
