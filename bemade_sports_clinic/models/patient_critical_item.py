"""Task 1677 — a player's allergies and medical conditions as structured
lists (owner 2026-10-24). Supersedes the #1654 hybrid model (free text +
structured life-threatening items only).

ONE model, ``sports.patient.critical.item``, kept from #1654 (its table,
ACL, team-scoped record rules, immutability and merge / Law 25 handling stay;
the staging data converts in place) — ``family`` says which list:

* ``allergy``: name + « Risque vital » (``life_threatening``);
* ``medical_alert`` (a condition): name + « Risque vital » + « Premiers
  soins » (``first_aid_note``).

EpiPen moved to the player (``allergy_epipen`` + ``allergy_epipen_note``,
the popup's EpiPen card). The family's level on the player is COMPUTED from
the list (sports.patient ``_compute_medical_levels``): red « Urgent » = a
life-threatening item, yellow « Not urgent » = items, none life-threatening,
« None known » = the empty list confirmed (``*_none_confirmed``), « Not
specified » otherwise. Adding an item drops the family's « none known ».

Only therapists (portal or internal) and clinic users write; coaches read
(record rules mirror the player's team access). Each change posts an
internal note on the player and stamps the family (« Updated on … by … »).
"""
from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .medical_alerts import DETAILS_FIELD, ITEM_NAME_MAX, LEVEL_MINOR, LEVEL_NONE, LEVEL_URGENT, fold

FAMILIES = [("allergy", "Allergy"), ("medical_alert", "Medical alert")]
LEVEL_FIELD = {"allergy": "allergy_level", "medical_alert": "medical_alert_level"}
NONE_FIELD = {"allergy": "allergy_none_confirmed", "medical_alert": "medical_none_confirmed"}
ITEM_FIELDS = ("name", "life_threatening", "first_aid_note")


def _fold(text):
    """Accent- and case-insensitive key of an item's name (merges)."""
    return fold(text)


class PatientCriticalItem(models.Model):
    _name = "sports.patient.critical.item"
    _description = "Allergy / medical condition of a player"
    _order = "sequence, id"

    patient_id = fields.Many2one("sports.patient", string="Player", required=True,
                                 ondelete="cascade", index=True)
    family = fields.Selection(FAMILIES, required=True, default="allergy")
    name = fields.Char(string="Name", required=True)
    life_threatening = fields.Boolean(string="Life-threatening")
    first_aid_note = fields.Text(string="First aid")
    sequence = fields.Integer(default=10)

    @api.constrains("name")
    def _check_name(self):
        for item in self:
            if not (item.name or "").strip():
                raise ValidationError(_("Please fill in all required fields."))

    # ------------------------------------------------------------ rules
    def _sc_check_writer(self):
        """Coaches read, never write (also through RPC): therapists (portal
        or internal), internal clinic users and the superuser write."""
        env = self.env
        if env.su or not env.user.share:
            return
        if env.user.has_group("bemade_sports_clinic.group_portal_treatment_professional"):
            return
        raise AccessError(_("Only the therapists can change the medical information."))

    def _sc_check_owner_change(self, vals):
        """Adversarial review 2026-10-22: the record rules are checked on the
        record BEFORE a write only — an item created on one's own player must
        never be moved onto another player (or family). Only the superuser
        (merges, scripts) re-parents an item."""
        if self.env.su:
            return
        for name in ("patient_id", "family"):
            if name not in vals:
                continue
            new = vals[name]
            if name == "patient_id":
                new = new.id if isinstance(new, models.BaseModel) else (new or False)
            for item in self:
                old = item.patient_id.id if name == "patient_id" else item.family
                if old != new:
                    raise AccessError(_("A medical item can't be moved to another player or family."))

    @staticmethod
    def _sc_clean_vals(vals):
        if "name" in vals:
            vals["name"] = (vals["name"] or "").strip()[:ITEM_NAME_MAX * 2]
        if "first_aid_note" in vals:
            vals["first_aid_note"] = (vals["first_aid_note"] or "").strip() or False
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        self._sc_check_writer()
        vals_list = [self._sc_clean_vals(dict(vals)) for vals in vals_list]
        # Task 1717: allergies wait for the EpiPen answer (scripts exempt).
        if not self.env.su:
            Patient = self.env['sports.patient'].sudo()
            for vals in vals_list:
                if vals.get('family') == 'allergy' and vals.get('patient_id') \
                        and not Patient.browse(vals['patient_id']).allergy_epipen_state:
                    raise ValidationError(Patient._sc_epipen_first_message())
        items = super().create(vals_list)
        # An item on the list: « none known » no longer holds.
        for (patient, family) in {(item.patient_id, item.family) for item in items}:
            if patient.sudo()[NONE_FIELD[family]]:
                patient.sudo().with_context(sc_critical_sync=True, tracking_disable=True).write(
                    {NONE_FIELD[family]: False})
        if not self.env.context.get("sc_critical_quiet"):
            items._sc_sync_patients("added")
        return items

    def write(self, vals):
        self._sc_check_writer()
        self._sc_check_owner_change(vals)
        vals = self._sc_clean_vals(dict(vals))
        changed = self.filtered(lambda item: any(
            name in vals and item[name] != vals[name] for name in ITEM_FIELDS))
        res = super().write(vals)
        if changed and not self.env.context.get("sc_critical_quiet"):
            changed._sc_sync_patients("changed")
        return res

    def unlink(self):
        self._sc_check_writer()
        pairs = [(item.patient_id, item.family, item.name) for item in self]
        res = super().unlink()
        if self.env.context.get("sc_critical_quiet"):
            return res  # Law 25 anonymization / merges: no note
        for patient, family, name in pairs:
            if patient.exists():
                patient.sudo()._sc_critical_sync(family, "removed", name)
        return res

    def _sc_sync_patients(self, what):
        for item in self:
            item.patient_id.sudo()._sc_critical_sync(item.family, what, item.name, item=item)

    def _sc_read_dict(self):
        """What the popups and the legacy pages show of ONE item."""
        self.ensure_one()
        item = self.sudo()
        return {
            "id": item.id,
            "family": item.family,
            "name": item.name,
            "life_threatening": bool(item.life_threatening),
            "first_aid_note": (item.first_aid_note or "").strip(),
        }


class Patient(models.Model):
    _inherit = "sports.patient"

    critical_item_ids = fields.One2many("sports.patient.critical.item", "patient_id",
                                        string="Allergies and conditions")
    allergy_critical_ids = fields.One2many(
        "sports.patient.critical.item", "patient_id", string="Allergies (list)",
        domain=[("family", "=", "allergy")])
    medical_alert_critical_ids = fields.One2many(
        "sports.patient.critical.item", "patient_id", string="Medical conditions",
        domain=[("family", "=", "medical_alert")])
    allergy_updated_info = fields.Char(string="Allergies updated", readonly=True, copy=False)
    medical_alert_updated_info = fields.Char(string="Medical alert updated", readonly=True, copy=False)

    def _sc_critical_items(self, family):
        self.ensure_one()
        return self.sudo().critical_item_ids.filtered(lambda i: i.family == family)

    def _sc_medical_stamp(self):
        return self.env._("Updated on %(date)s by %(author)s",
                          date=fields.Date.to_string(fields.Date.context_today(self)),
                          author=self.env.user.name or "—")

    def _sc_critical_sync(self, family, what, name, item=None):
        """After an item change: the family is stamped and an internal note
        records the change (the level follows by its compute)."""
        self.ensure_one()
        self.with_context(sc_critical_sync=True, tracking_disable=True).write(
            {"%s_updated_info" % family: self._sc_medical_stamp()})
        label = dict(self.env["sports.patient.critical.item"]._fields["family"]._description_selection(self.env))[family]
        verbs = {"added": self.env._("added"), "changed": self.env._("changed"), "removed": self.env._("removed")}
        body = Markup("%s · %s : <b>%s</b>") % (label, verbs.get(what, what), escape(name or ""))
        if item is not None and item.exists() and item.life_threatening and what != "removed":
            body += Markup(" (%s)") % self.env._("life-threatening")
        self.message_post(body=body, subtype_xmlid="mail.mt_note")

    @api.depends("critical_item_ids.family", "critical_item_ids.life_threatening",
                 "allergy_none_confirmed", "medical_none_confirmed")
    def _compute_medical_levels(self):
        """Task 1677: red / yellow / grey from the lists. « None known » only
        for an EMPTY list confirmed; an empty list not confirmed stays « Not
        specified » (the #1628 To-Do still asks for it)."""
        for patient in self:
            items = patient.sudo().critical_item_ids
            for family, level_field in LEVEL_FIELD.items():
                mine = items.filtered(lambda i, f=family: i.family == f)
                if any(mine.mapped("life_threatening")):
                    level = LEVEL_URGENT
                elif mine:
                    level = LEVEL_MINOR
                elif patient.sudo()[NONE_FIELD[family]]:
                    level = LEVEL_NONE
                else:
                    level = False
                patient[level_field] = level
