from odoo import fields, models


class CbetCompetencyVersion(models.Model):
    """UC-CAT-09 AC1 — an immutable snapshot of a competency's criteria,
    questions and protocol, frozen at publication time. Evaluations pin the
    version they were run against (UC-EVL-03/10)."""

    _name = "cbet.competency.version"
    _description = "CBET Competency Published Version"
    _order = "publish_date desc, id desc"

    competency_id = fields.Many2one(
        "cbet.competency", required=True, ondelete="cascade", index=True,
    )
    version = fields.Char(required=True)
    publish_date = fields.Date(required=True)
    snapshot = fields.Json(
        help="Frozen criteria/questions/protocol at publication time.",
    )

    def _snapshot_payload(self, competency):
        return {
            "code": competency.code,
            "name": competency.name,
            "kind": competency.kind,
            "pass_threshold": competency.pass_threshold,
            "validity_months": competency.validity_months,
            "reprise_deadline_days": competency.reprise_deadline_days,
            "protocol": {
                "method": competency.protocol_method,
                "place": competency.protocol_place,
                "duration": competency.protocol_duration,
                "support": competency.protocol_support,
                "min_evaluator_qualification": competency.protocol_min_evaluator_qualification,
            },
            "units": [
                {
                    "id": unit.id,
                    "name": unit.name,
                    "required": unit.required,
                    "criteria": [
                        {
                            "id": c.id,
                            "sequence": c.sequence,
                            "type": c.criterion_type,
                            "text": c.text,
                            "verification_method": c.verification_method,
                            "tolerance": c.tolerance,
                        }
                        for c in unit.criterion_ids
                    ],
                }
                for unit in competency.unit_ids
            ],
            "questions": [
                {
                    "id": q.id,
                    "sequence": q.sequence,
                    "text": q.text,
                    "expected_answer": q.expected_answer,
                    "section_ref": q.section_ref,
                    "essential": q.essential,
                }
                for q in competency.question_ids
            ],
        }

    def _snapshot(self, competency):
        """Create and return the frozen version record for a competency."""
        return self.create({
            "competency_id": competency.id,
            "version": competency.version,
            "publish_date": competency.publish_date,
            "snapshot": self._snapshot_payload(competency),
        })
