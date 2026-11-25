from odoo import Command, fields
from odoo.tests import TransactionCase, new_test_user

LEVEL_NAMES_EN = {
    3: ["Below", "Meets", "Above"],
    4: ["Poor", "Fair", "Good", "Excellent"],
    5: ["Very low", "Low", "Medium", "High", "Very high"],
}
LEVEL_NAMES_FR = {
    3: ["Sous", "Atteint", "Au-dessus"],
    4: ["Faible", "Passable", "Bon", "Excellent"],
    5: ["Très bas", "Bas", "Moyen", "Haut", "Très haut"],
}


class CampaignCase(TransactionCase):
    """Synthetic company: an employee, their manager, a colleague, a director who
    calibrates and an HR officer; a rating scale of ``LEVELS`` levels with two sections
    (``SECTION_SIZES`` criteria each) and one word picture per level."""

    LEVELS = 5
    SECTION_SIZES = (2, 3)

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("en_US")
        cls.env["res.lang"]._activate_lang("fr_FR")
        cls.env["ir.module.module"]._load_module_terms(["hr_appraisal_campaign"], ["fr_FR"])
        cls.scale = cls.make_scale(cls.LEVELS)
        cls.sections, cls.criteria = cls.make_catalogue(cls.scale, cls.SECTION_SIZES)

        cls.hr_user = new_test_user(
            cls.env, login="hac_hr", name="Test HR Officer",
            groups="base.group_user,hr_appraisal.group_hr_appraisal_user")
        cls.manager_user = new_test_user(
            cls.env, login="hac_mgr", name="Test Manager Beta", groups="base.group_user")
        cls.employee_user = new_test_user(
            cls.env, login="hac_emp", name="Test Employee Alpha", groups="base.group_user",
            lang="fr_FR")
        cls.colleague_user = new_test_user(
            cls.env, login="hac_col", name="Test Colleague Gamma", groups="base.group_user")
        cls.director_user = new_test_user(
            cls.env, login="hac_dir", name="Test Director Delta",
            groups="base.group_user,hr_appraisal_campaign.group_campaign_calibration")

        Employee = cls.env["hr.employee"]
        cls.director = Employee.create({"name": "Test Director Delta", "user_id": cls.director_user.id})
        cls.manager = Employee.create({
            "name": "Test Manager Beta", "user_id": cls.manager_user.id, "parent_id": cls.director.id})
        cls.job = cls.env["hr.job"].create({"name": "Synthetic Technician"})
        cls.employee = Employee.create({
            "name": "Test Employee Alpha", "user_id": cls.employee_user.id,
            "parent_id": cls.manager.id, "job_id": cls.job.id})
        cls.colleague = Employee.create({
            "name": "Test Colleague Gamma", "user_id": cls.colleague_user.id,
            "parent_id": cls.manager.id})
        cls.no_user = Employee.create({"name": "Test Paper Epsilon", "parent_id": cls.manager.id})

        cls.campaign = cls.env["hr.appraisal.campaign"].with_user(cls.hr_user).create({
            "name": "Synthetic Campaign",
            "scale_id": cls.scale.id,
            "date_start": "2026-01-01",
            "date_end": "2026-12-31",
            "deadline_self_eval": "2026-12-01",
            "deadline_manager": "2026-12-10",
            "deadline_calibration": "2026-12-15",
            "deadline_meetings": "2026-12-20",
            "employee_ids": [Command.set((cls.employee | cls.colleague | cls.no_user).ids)],
        })

    # ------------------------------------------------------------------ builders
    @classmethod
    def make_scale(cls, n, name=None):
        scale = cls.env["hr.appraisal.campaign.scale"].with_context(lang="en_US").create({
            "name": name or f"Synthetic {n}-level scale",
            "level_ids": [
                Command.create({"value": i + 1, "name": LEVEL_NAMES_EN[n][i]}) for i in range(n)
            ],
        })
        for level, fr_name in zip(scale.level_ids, LEVEL_NAMES_FR[n]):
            level.with_context(lang="fr_FR").name = fr_name
        return scale

    @classmethod
    def make_catalogue(cls, scale, sizes):
        Section = cls.env["hr.appraisal.campaign.section"].with_context(lang="en_US")
        Criterion = cls.env["hr.appraisal.campaign.criterion"].with_context(lang="en_US")
        sections = Section.browse()
        criteria = Criterion.browse()
        for s_index, size in enumerate(sizes, start=1):
            section = Section.create({
                "name": f"Section {s_index}", "sequence": s_index, "scale_id": scale.id})
            section.with_context(lang="fr_FR").name = f"Volet {s_index}"
            sections |= section
            for c_index in range(1, size + 1):
                criterion = Criterion.create({
                    "section_id": section.id,
                    "sequence": c_index,
                    "name": f"Criterion {s_index}.{c_index}",
                    "description": f"What criterion {s_index}.{c_index} looks at",
                })
                criterion.with_context(lang="fr_FR").name = f"Critère {s_index}.{c_index}"
                for level_line in criterion.level_ids:
                    value = level_line.value
                    level_line.with_context(lang="en_US").description = (
                        f"EN picture {s_index}.{c_index} level {value}")
                    level_line.with_context(lang="fr_FR").description = (
                        f"Portrait FR {s_index}.{c_index} niveau {value}")
                criteria |= criterion
        return sections, criteria

    @classmethod
    def set_thresholds(cls, owner, section, mins):
        """``mins``: {level value: min points}; owner = scale (overall), section or campaign."""
        scale = owner.scale_id if owner._name != "hr.appraisal.campaign.scale" else owner
        Threshold = cls.env["hr.appraisal.campaign.threshold"]
        existing = Threshold.search([
            ("campaign_id", "=", owner.id if owner._name == "hr.appraisal.campaign" else False),
            ("section_id", "=", section.id if section else False),
            ("scale_id", "=", scale.id),
        ])
        existing.unlink()
        for value, min_score in mins.items():
            Threshold.create({
                "campaign_id": owner.id if owner._name == "hr.appraisal.campaign" else False,
                "section_id": section.id if section else False,
                "scale_id": scale.id,
                "level_id": scale.level_ids.filtered(lambda lv, v=value: lv.value == v).id,
                "min_score": min_score,
            })

    # ------------------------------------------------------------------ flow helpers
    @property
    def n_criteria(self):
        return len(self.criteria)

    def launch(self):
        self.campaign.with_user(self.hr_user).action_launch()
        return self.campaign.appraisal_ids.filtered(lambda a: a.employee_id == self.employee)

    def set_self(self, appraisal, grades, user=None):
        for line, grade in zip(appraisal.campaign_line_ids, grades):
            line.with_user(user or self.employee_user).write({"employee_grade_ui": grade})

    def set_manager(self, appraisal, grades, user=None):
        for line, grade in zip(appraisal.campaign_line_ids, grades):
            line.with_user(user or self.manager_user).write({"manager_grade_ui": grade})

    def run_to_calibration(self, self_grade=3, manager_grade=3):
        appraisal = self.launch()
        self.set_self(appraisal, [self_grade] * self.n_criteria)
        appraisal.with_user(self.employee_user).action_campaign_submit_self()
        self.set_manager(appraisal, [manager_grade] * self.n_criteria)
        appraisal.with_user(self.manager_user).action_campaign_submit_manager()
        return appraisal

    def to_meeting(self, appraisal_grades=(3, 3)):
        appraisal = self.run_to_calibration(*appraisal_grades)
        self.campaign.with_user(self.hr_user).action_start_calibration()
        self.campaign.with_user(self.hr_user).action_close_calibration()
        return appraisal

    @staticmethod
    def today():
        return fields.Date.today()
