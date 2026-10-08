from odoo import fields, models


class CbetCompetencyVersion(models.Model):
    """UC-CAT-09 AC1 — an immutable snapshot of a competency's criteria,
    questions, protocol and documents (fiche sections, procedure, job aids,
    demo notes), frozen at publication time. Evaluations pin the version they
    were run against (UC-EVL-03/10)."""

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
            "lang": competency.env.lang or "en_US",
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
                "start_conditions": competency.protocol_start_conditions,
                "verbalization": competency.protocol_verbalization,
                "min_evaluator_qualification": competency.protocol_min_evaluator_qualification,
                "evaluator_independence": competency.evaluator_independence,
            },
            "validity": {
                "maintenance_condition": competency.maintenance_condition,
                "recert_modality": competency.recert_modality,
                "recert_early_trigger": competency.recert_early_trigger,
            },
            # The fiche sections and the operational documents, as published.
            # Single-language (the publishing user's), as the rest of the
            # snapshot; consumers use .get() since older versions lack them.
            "subtitle": competency.subtitle,
            "execution_context": competency.execution_context,
            "knowledge_body": competency.knowledge_body,
            "safety_block": competency.safety_block,
            "tools_materials": competency.tools_materials,
            "documents_required": competency.documents_required,
            "evidence_required": competency.evidence_required,
            "references_body": competency.references_body,
            "procedure_body": competency.procedure_body,
            "demo_notes_body": competency.demo_notes_body,
            "meta": {
                "field_frequency": competency.field_frequency,
                "difficulty": competency.difficulty,
                "learning_time": competency.learning_time,
                "common_pitfalls": competency.common_pitfalls,
            },
            "prerequisites": [
                {"code": edge.prerequisite_id.code, "type": edge.prereq_type}
                for edge in competency.prerequisite_ids
            ],
            "job_aids": [
                {
                    "id": aid.id,
                    "variant": aid.variant,
                    "sections": [
                        {
                            "face": s.face,
                            "kind": s.kind,
                            "icon": s.icon_id.token,
                            "name": s.name,
                            "note_html": s.note_html,
                            "lines": [
                                {"icon": ln.icon_id.token, "text": ln.text}
                                for ln in s.line_ids
                            ],
                        }
                        for s in aid.section_ids
                    ],
                }
                for aid in competency.job_aid_ids
            ],
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
