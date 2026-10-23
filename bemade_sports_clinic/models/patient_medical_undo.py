"""Owner review 2026-10-22 (#1653 / #1654) — « Annuler » after « Aucune ».

Choosing « None known » for an allergy / medical alert clears the family's
details (and EpiPen, and its life-threatening items). An accidental clear is
undone from the toast the save answers (« Details cleared · Undo »):

* before the clearing write, the app save takes a ONE-SHOT snapshot of the
  family (level, details, EpiPen, items) in ``sports.patient.medical.undo``
  — a short-lived record, the same author-and-window guard as the inline
  creations' undo (``SC_MEDICAL_UNDO_MINUTES``);
* ``POST /my/app/medical/undo/<id>`` (controllers/app_critical_items.py)
  restores it: the same user, within the window, while the family is still
  « None known »; the snapshot is consumed either way;
* the autovacuum drops the expired ones (a snapshot holds medical text, it
  never outlives its window by more than a day); they also go with the
  player (cascade) and on a Law 25 anonymization.

Only what a therapist can edit is snapshotted: coaches never reach the save.
"""
import secrets
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

from .medical_alerts import LEVEL_MINOR, LEVEL_NONE, LEVEL_URGENT
from .patient_critical_item import DETAILS_FIELD, LEVEL_FIELD

SC_MEDICAL_UNDO_MINUTES = 2
FAMILY_OF_LEVEL = {level: family for family, level in LEVEL_FIELD.items()}


class PatientMedicalUndo(models.Model):
    _name = "sports.patient.medical.undo"
    _description = "Undo snapshot of a cleared allergy / medical alert"

    patient_id = fields.Many2one("sports.patient", required=True, ondelete="cascade", index=True)
    user_id = fields.Many2one("res.users", required=True, ondelete="cascade")
    family = fields.Selection([("allergy", "Allergy"), ("medical_alert", "Medical alert")], required=True)
    token = fields.Char(required=True, copy=False)
    snapshot = fields.Json(required=True)

    def _sc_expired(self):
        self.ensure_one()
        deadline = fields.Datetime.now() - timedelta(minutes=SC_MEDICAL_UNDO_MINUTES)
        return not self.create_date or self.create_date < deadline

    @api.autovacuum
    def _gc_expired(self):
        deadline = fields.Datetime.now() - timedelta(minutes=SC_MEDICAL_UNDO_MINUTES)
        self.sudo().search([("create_date", "<", deadline)]).unlink()


class Patient(models.Model):
    _inherit = "sports.patient"

    def _sc_medical_snapshot(self, family):
        """The family as it is now, or None when « None known » would clear
        nothing (no details, no EpiPen, no item)."""
        self.ensure_one()
        patient = self.sudo()
        level_field = LEVEL_FIELD[family]
        items = patient._sc_critical_items(family)
        details = patient[DETAILS_FIELD[family]] or False
        epipen = bool(family == "allergy" and patient.allergy_epipen)
        if patient[level_field] == LEVEL_NONE or not (items or (details or "").strip() or epipen):
            return None
        return {
            "level": patient[level_field] or False,
            "details": details,
            "epipen": epipen,
            "items": [{"name": item.name, "epipen": item.epipen, "action": item.action or False,
                       "sequence": item.sequence} for item in items],
        }

    def _sc_medical_undo_offer(self, family, snapshot):
        """Store ``snapshot`` (one per player, family and user: a newer clear
        replaces the older offer) and return the save answer's ``undo``."""
        self.ensure_one()
        Undo = self.env["sports.patient.medical.undo"].sudo()
        Undo.search([("patient_id", "=", self.id), ("family", "=", family),
                     ("user_id", "=", self.env.user.id)]).unlink()
        undo = Undo.create({
            "patient_id": self.id, "user_id": self.env.user.id, "family": family,
            "token": secrets.token_urlsafe(16), "snapshot": snapshot,
        })
        return {
            "url": "/my/app/medical/undo/%s" % undo.id,
            "token": undo.token,
            "message": self.env._("Details cleared"),
            "action": self.env._("Undo"),
            "ms": SC_MEDICAL_UNDO_MINUTES * 60 * 1000,
        }

    def _sc_medical_undo_restore(self, undo):
        """Put the snapshot back, as the current user (the medical rules and
        the item sync apply: the items bring « Urgent » and EpiPen back, each
        posts its note, the family is stamped)."""
        self.ensure_one()
        family = undo.family
        level_field = LEVEL_FIELD[family]
        if self.sudo()[level_field] != LEVEL_NONE:
            raise UserError(self.env._("These details were changed since; they can no longer be restored."))
        snap = dict(undo.snapshot or {})
        level = snap.get("level") or False
        vals = {
            # « Urgent » comes back with its items (an item forces it).
            level_field: LEVEL_MINOR if level == LEVEL_URGENT else level,
            DETAILS_FIELD[family]: snap.get("details") or False,
        }
        if family == "allergy":
            vals["allergy_epipen"] = bool(snap.get("epipen"))
        # A level that was never set (legacy text without a level) can't be
        # written back through the rules (« Please choose a level »): that
        # rare case is put back as is, like an import.
        (self if level else self.sudo().with_context(sc_phone_lenient=True)).write(vals)
        items = [dict(item, patient_id=self.id, family=family)
                 for item in snap.get("items") or [] if item.get("name")]
        if items:
            self.env["sports.patient.critical.item"].create(items)
        if level == LEVEL_URGENT and family == "allergy" and snap.get("epipen") and not self.allergy_epipen:
            self.write({"allergy_epipen": True})
        return True
