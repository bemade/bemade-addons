from odoo import Command
from odoo.tests.common import TransactionCase


class CbetCommon(TransactionCase):
    """Shared fixtures for hr_skills_cbet tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company

        # A CBET Manager user (needed for publication / catalog edits).
        cls.manager = cls.env["res.users"].create({
            "name": "CBET Manager",
            "login": "cbet_manager",
            "email": "cbet_manager@example.com",
            "group_ids": [Command.link(cls.env.ref("hr_skills_cbet.group_cbet_manager").id)],
        })

        cls.evaluator = cls.env["res.users"].create({
            "name": "CBET Evaluator",
            "login": "cbet_evaluator",
            "email": "cbet_evaluator@example.com",
            "group_ids": [Command.link(cls.env.ref("hr_skills_cbet.group_cbet_evaluator").id)],
        })

        cls.domain = cls.env["cbet.domain"].create({"code": "TST", "name": "Test domain"})

    @classmethod
    def _publish(cls, competency):
        competency.with_user(cls.manager).action_publish()
        return competency

    @classmethod
    def _ready_competency(cls, code="TST-99", crit_specs=None, question_specs=None,
                          evaluator=None, kind="procedural"):
        """A published competency with criteria/questions and a designated
        evaluator, ready to be evaluated."""
        comp = cls._make_competency(code, kind=kind)
        if kind != "theoretical":
            cls._add_criteria(comp, crit_specs or [("standard", "Do the thing")])
        for spec in (question_specs or []):
            cls.env["cbet.question"].create({
                "competency_id": comp.id, "text": spec[0], "essential": spec[1],
            })
        comp.designated_trainer_ids = (evaluator or cls.evaluator)
        cls._publish(comp)
        return comp

    @classmethod
    def _make_competency(cls, code="TST-01", **vals):
        base = {"code": code, "name": "Competency %s" % code, "domain_id": cls.domain.id}
        base.update(vals)
        return cls.env["cbet.competency"].create(base)

    @classmethod
    def _add_criteria(cls, competency, specs):
        """specs: list of (type, text) tuples added to the competency's first unit."""
        unit = competency.unit_ids[:1]
        return cls.env["cbet.criterion"].create([
            {"unit_id": unit.id, "criterion_type": t, "text": txt}
            for (t, txt) in specs
        ])

    @classmethod
    def _make_employee(cls, name="Technician"):
        return cls.env["hr.employee"].create({"name": name})

    @classmethod
    def _make_cert_skill(cls, name="Tech Classe I"):
        """Create a certification hr.skill (with type + level) for tie-back tests."""
        skill_type = cls.env["hr.skill.type"].create({
            "name": "CBET Certifications %s" % name,
            "is_certification": True,
            "skill_ids": [Command.create({"name": name})],
            "skill_level_ids": [
                Command.create({"name": "Certified", "level_progress": 100}),
            ],
        })
        return skill_type.skill_ids[0]

    @classmethod
    def _make_standard(cls, name="Classe I", essentials=None, skill=None):
        std = cls.env["cbet.standard"].create({
            "name": name,
            "skill_id": skill.id if skill else False,
            "line_ids": [
                Command.create({"competency_id": c.id, "line_type": "essential"})
                for c in (essentials or [])
            ],
        })
        return std

    @classmethod
    def _make_evaluation(cls, competency, candidate, unit=None, evaluator=None):
        ev = cls.env["cbet.evaluation"].create({
            "competency_id": competency.id,
            "unit_id": (unit or competency.unit_ids[:1]).id,
            "candidate_id": candidate.id,
            "evaluator_id": (evaluator or cls.evaluator).id,
        })
        ev.action_start()
        return ev

    @staticmethod
    def _set_results(ev, crit="reussi", question="acquis"):
        for line in ev.criterion_result_ids:
            line.result = crit
        for line in ev.question_result_ids:
            line.result = question

    @staticmethod
    def _sign_and_complete(ev, decision="reussi"):
        import base64
        sig = base64.b64encode(b"signature")
        ev.write({
            "decision": decision,
            "evaluator_signature": sig,
            "candidate_signature": sig,
        })
        ev.action_complete()
        return ev

    @classmethod
    def _certify(cls, employee, competency, valid_from=None, valid_to=None):
        return cls.env["cbet.certification"].create({
            "employee_id": employee.id,
            "competency_id": competency.id,
            "valid_from": valid_from or cls.env["cbet.certification"].default_get(
                ["valid_from"])["valid_from"],
            "valid_to": valid_to,
        })
