"""Task 1654 — the life-threatening items of a player's allergies / medical
alerts (hybrid model, owner 2026-10-22).

The free-text details stay the capture field; only what is life-threatening
becomes a structured item: a name, EpiPen (allergies only) and a short
« conduite à tenir ». The family's level follows the items:

* « Urgent – life-threatening » ⇔ at least one item (an item added forces it;
  Urgent can't be chosen without one — sports.patient._sc_medical_level_rules);
* the last item removed → « Not urgent » when details remain, else « None
  known »;
* EpiPen on the player (``allergy_epipen``) follows the allergy items while
  there are some.

Only therapists (portal or internal) and clinic users write; coaches read
(record rules mirror the player's team access). Each change posts an
internal note on the player and stamps the family (« Updated on … by … »).

``suggest_critical_items(family, text)`` is the rule-based suggester the
19.0.1.107.0 migration uses (the hook a later AI suggester replaces, #1657).
"""
import re
import unicodedata

from markupsafe import Markup, escape

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .medical_alerts import LEVEL_MINOR, LEVEL_NONE, LEVEL_URGENT

FAMILIES = [("allergy", "Allergy"), ("medical_alert", "Medical alert")]
LEVEL_FIELD = {"allergy": "allergy_level", "medical_alert": "medical_alert_level"}
DETAILS_FIELD = {"allergy": "allergy_details", "medical_alert": "medical_alert_details"}
ITEM_NAME_MAX = 60

_SPLIT_RE = re.compile(r"\s*(?:[,;\n/]+|\s+et\s+|\s+and\s+)\s*", re.IGNORECASE)
_URGENT_CUES = ("epipen", "epi-pen", "epi pen", "severe", "anaphyla", "mortel", "mortelle",
                "choc", "shock", "life-threatening", "vital", "grave")
_EPIPEN_CUES = ("epipen", "epi-pen", "epi pen", "auto-injecteur", "auto injecteur")


def _fold(text):
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def _clean_segment(segment):
    segment = re.sub(r"\(.*?\)", " ", segment)
    segment = re.sub(r"\b(?:epi-?pen|epi pen|s[eé]v[eè]re|anaphylaxie|anaphylactique|mortelle?|"
                     r"choc|grave|allergies?|allergiques?|a|à)\b", " ", segment, flags=re.IGNORECASE)
    segment = re.sub(r"\s+", " ", segment).strip(" .:-–")
    return segment


def suggest_critical_items(family, text, epipen=False):
    """Rule-based suggestions ``[{name, epipen, action}]`` from a family's
    free text: the segments (commas, semicolons, lines, « et » / « and »)
    carrying an urgent cue (EpiPen, sévère / severe, anaphyla*, mortel, choc…),
    else the whole text as one item. EpiPen when the segment mentions it, or
    when the player had EpiPen and there is only one item."""
    raw = (text or "").strip()
    if not raw:
        return []
    segments = [seg for seg in _SPLIT_RE.split(raw) if seg.strip()]
    picked = [seg for seg in segments if any(cue in _fold(seg) for cue in _URGENT_CUES)]
    if not picked:
        picked = [raw]
    items = []
    for seg in picked:
        name = _clean_segment(seg) or seg.strip()
        name = name[:ITEM_NAME_MAX].strip()
        if not name:
            continue
        mentions = any(cue in _fold(seg) for cue in _EPIPEN_CUES)
        items.append({"name": name, "epipen": family == "allergy" and mentions, "action": False})
    if family == "allergy" and epipen and len(items) == 1:
        items[0]["epipen"] = True
    seen, unique = set(), []
    for item in items:
        key = _fold(item["name"])
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


class PatientCriticalItem(models.Model):
    _name = "sports.patient.critical.item"
    _description = "Critical medical item (life-threatening allergy / condition)"
    _order = "sequence, id"

    patient_id = fields.Many2one("sports.patient", string="Player", required=True,
                                 ondelete="cascade", index=True)
    family = fields.Selection(FAMILIES, required=True, default="allergy")
    name = fields.Char(string="Critical item", required=True)
    epipen = fields.Boolean(string="EpiPen")
    action = fields.Text(string="What to do")
    sequence = fields.Integer(default=10)

    @api.constrains("epipen", "family")
    def _check_epipen_allergy_only(self):
        for item in self:
            if item.epipen and item.family != "allergy":
                raise ValidationError(_("EpiPen goes with an allergy only."))

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

    @api.model_create_multi
    def create(self, vals_list):
        self._sc_check_writer()
        for vals in vals_list:
            if vals.get("name"):
                vals["name"] = vals["name"].strip()[:ITEM_NAME_MAX * 2]
        items = super().create(vals_list)
        if not self.env.context.get("sc_critical_quiet"):
            items._sc_sync_patients("added")
        return items

    def write(self, vals):
        self._sc_check_writer()
        res = super().write(vals)
        if not self.env.context.get("sc_critical_quiet"):
            self._sc_sync_patients("changed")
        return res

    def unlink(self):
        self._sc_check_writer()
        pairs = [(item.patient_id, item.family, item.name) for item in self]
        res = super().unlink()
        if self.env.context.get("sc_critical_quiet"):
            return res  # Law 25 anonymization / merges: no note, no level change
        for patient, family, name in pairs:
            if patient.exists():
                patient.sudo()._sc_critical_sync(family, "removed", name)
        return res

    def _sc_sync_patients(self, what):
        for item in self:
            item.patient_id.sudo()._sc_critical_sync(item.family, what, item.name)


class Patient(models.Model):
    _inherit = "sports.patient"

    critical_item_ids = fields.One2many("sports.patient.critical.item", "patient_id",
                                        string="Critical items")
    allergy_critical_ids = fields.One2many(
        "sports.patient.critical.item", "patient_id", string="Critical allergies",
        domain=[("family", "=", "allergy")])
    medical_alert_critical_ids = fields.One2many(
        "sports.patient.critical.item", "patient_id", string="Critical conditions",
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

    def _sc_critical_sync(self, family, what, name):
        """After an item change: the level follows (urgent ⇔ items), EpiPen
        follows the allergy items, the family is stamped and an internal note
        records the change."""
        self.ensure_one()
        items = self._sc_critical_items(family)
        level_field = LEVEL_FIELD[family]
        vals = {}
        if items:
            if self[level_field] != LEVEL_URGENT:
                vals[level_field] = LEVEL_URGENT
            if family == "allergy":
                epipen = any(items.mapped("epipen"))
                if bool(self.allergy_epipen) != epipen:
                    vals["allergy_epipen"] = epipen
        elif what == "removed" and self[level_field] == LEVEL_URGENT:
            vals[level_field] = LEVEL_MINOR if (self[DETAILS_FIELD[family]] or "").strip() else LEVEL_NONE
            if family == "allergy":
                vals["allergy_epipen"] = False
        vals["%s_updated_info" % family] = self._sc_medical_stamp()
        self.with_context(sc_critical_sync=True, tracking_disable=True).write(vals)
        label = dict(self.env["sports.patient.critical.item"]._fields["family"]._description_selection(self.env))[family]
        verbs = {"added": self.env._("added"), "changed": self.env._("changed"), "removed": self.env._("removed")}
        body = Markup("%s · %s : <b>%s</b>") % (label, verbs.get(what, what), escape(name or ""))
        self.message_post(body=body, subtype_xmlid="mail.mt_note")

    def _sc_create_suggested_items(self):
        """Task 1654: « Urgent » families without items get the suggester's
        items from their details (player creation)."""
        Item = self.env["sports.patient.critical.item"].sudo().with_context(sc_critical_quiet=True)
        for patient in self:
            for family, level_field in LEVEL_FIELD.items():
                if patient[level_field] != LEVEL_URGENT or patient._sc_critical_items(family):
                    continue
                suggestions = suggest_critical_items(
                    family, patient[DETAILS_FIELD[family]],
                    epipen=family == "allergy" and patient.allergy_epipen)
                Item.create([dict(s, patient_id=patient.id, family=family, sequence=10 + n)
                             for n, s in enumerate(suggestions)])
