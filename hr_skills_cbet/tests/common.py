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

    # ------------------------------------------------------------------
    # UC-RPT-02/03/06 — synthetic documents for the PDF reports. Invented
    # wording only: nothing here comes from a real training vault.
    # ------------------------------------------------------------------
    FULL_FICHE = {
        "subtitle": "Recognition competency, demonstrated on a test bench",
        "execution_context": "<table><tr><td>Equipment covered</td>"
                             "<td>Synthetic bench XB-1</td></tr></table>",
        "knowledge_body": "<h3>Glossary</h3><ul><li><strong>Inlet</strong> — where the "
                          "water comes in.</li></ul>",
        "safety_block": "<ul><li>☐ Lock-out required — see the isolation competency</li></ul>",
        "tools_materials": "<ul><li>Standard tool bag</li><li>Conductivity meter</li></ul>",
        "documents_required": "<ul><li>Data form XF-1</li></ul>",
        "evidence_required": "<ul><li>Signed evaluation grid</li></ul>",
        "references_body": "<ol><li>Synthetic bench manual, rev. 3</li></ol>",
        "procedure_body": "<h2>Steps</h2><ol><li>Isolate the bench.</li>"
                          "<li>Open the lid.</li></ol>",
        "demo_notes_body": "<h2>Step 1 — Prepare</h2><p>Set up the bench before the "
                           "technician arrives.</p>",
        "protocol_method": "Demonstration on the test bench",
        "protocol_place": "Training room",
        "protocol_duration": 0.75,
        "protocol_support": "Written procedure allowed, no verbal help",
        "protocol_start_conditions": "Bench in service",
        "protocol_verbalization": "Explain each key step aloud",
        "protocol_min_evaluator_qualification": "Designated trainer",
        "evaluator_independence": "Preferably not the candidate's direct trainer",
        "validity_months": 24,
        "maintenance_condition": "At least 3 interventions of this kind in 12 months",
        "recert_modality": "Light demonstration (key criteria only)",
        "recert_early_trigger": "Incident or major procedure change",
        "field_frequency": "★★★ — frequent",
        "difficulty": "medium",
        "learning_time": "2 h demo + 4 h supervised practice",
        "common_pitfalls": "Confuses the inlet with the outlet",
    }

    @classmethod
    def _make_full_competency(cls, code="XPR-01", publish=True, **extra):
        """A competency with every fiche section, a mandatory prerequisite, three
        typed criteria and both operational bodies; published (v1.0) by default."""
        pcode = "XPQ-" + code.split("-")[1]
        prereq = cls.env["cbet.competency"].search([("code", "=", pcode)], limit=1)
        if not prereq:
            prereq = cls._make_competency(pcode, name="Safe isolation of a bench")
        vals = dict(cls.FULL_FICHE, name="Read the synthetic bench", **extra)
        comp = cls._make_competency(code, **vals)
        cls.env["cbet.prerequisite"].create({
            "competency_id": comp.id, "prerequisite_id": prereq.id,
            "prereq_type": "obligatoire",
        })
        cls._add_criteria(comp, [
            ("security", "Bench isolated before opening"),
            ("critical", "Readings within tolerance"),
            ("standard", "Data recorded on the form"),
        ])
        if publish:
            cls._publish(comp)
        return comp

    @classmethod
    def _make_job_aid(cls, comp, variant=False):
        """A recto/verso job aid: three recto blocks (PPE with icons, STOP, data)
        and two verso phases, the last one with a reference table."""
        icons = cls.env["cbet.icon"]._by_token()
        goggles, stop = icons["epi-lunettes"], icons["sev-stop"]
        return cls.env["cbet.job.aid"].create({
            "competency_id": comp.id,
            "variant": variant,
            "section_ids": [
                Command.create({
                    "face": "recto", "kind": "ppe", "icon_id": goggles.id, "name": "PPE",
                    "line_ids": [
                        Command.create({"icon_id": goggles.id, "text": "safety glasses"}),
                        Command.create({"text": "safety shoes"}),
                    ],
                }),
                Command.create({
                    "face": "recto", "kind": "stop", "icon_id": stop.id,
                    "name": "STOP — escalate",
                    "line_ids": [
                        Command.create({"text": "Bench under pressure — point, do not touch"}),
                    ],
                }),
                Command.create({
                    "face": "recto", "kind": "data", "name": "Data to record",
                    "line_ids": [
                        Command.create({"text": "Inlet pressure"}),
                        Command.create({"text": "Flow"}),
                    ],
                }),
                Command.create({
                    "face": "verso", "kind": "phase", "name": "1. State the principle",
                    "line_ids": [Command.create({"text": "Reading point defined aloud"})],
                }),
                Command.create({
                    "face": "verso", "kind": "phase", "icon_id": stop.id,
                    "name": "2. Check before leaving",
                    "line_ids": [Command.create({"icon_id": stop.id, "text": "Nothing touched"})],
                    "note_html": "<table><tr><td>Unit</td><td>kPa — inlet reading</td></tr></table>",
                }),
            ],
        })

    def _render(self, report_xmlid, records, lang=None):
        """The report's html as text (``lang`` switches the rendering language)."""
        Report = self.env["ir.actions.report"]
        if lang:
            Report = Report.with_context(lang=lang)
        html, _type = Report._render_qweb_html(report_xmlid, records.ids)
        return html.decode()

    @classmethod
    def _load_fr(cls):
        """Activate fr_CA and load the module's own translations for it."""
        cls.env["res.lang"]._activate_lang("fr_CA")
        cls.env["ir.module.module"]._load_module_terms(["hr_skills_cbet"], ["fr_CA"])
        return "fr_CA"
