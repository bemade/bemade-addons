"""Task 1677 — allergies and medical alerts as structured lists.

After the module loads (the pre-migrate converted the #1654 items in place):

* staging-like data — a family with #1654 items keeps them (now
  life-threatening items); its former details stay as the « Old text (to
  validate) » while the player is flagged;
* a family with former details (the 19.0.1.99.0 conversion, or typed since)
  and no item: the details are split into items by the rule-based suggester
  (``suggest_medical_items``: one item per segment, life-threatening on an
  urgent cue — « Not urgent » families get none — EpiPen OR'ed);
* a player with no level, no details and no item (prod: only the legacy
  ``allergies`` text — the 19.0.1.99.0 conversion is superseded): the text is
  split the same way into both lists; « aucune » and its variants tick
  « no known allergy / condition »;
* a family left « None known » ticks its « none known »;
* every player given items from a text is flagged « to validate »
  (``medical_alert_review``);
* the levels are recomputed for every player (they became computed fields
  on an existing column);
* the #1653 « Undo » snapshots table (``sports.patient.medical.undo``, a
  model removed with this version) is dropped — it held medical text and
  Odoo leaves the table of a removed model behind.

Idempotent (a family with items is never converted again; a ticked « none
known » is ticked again); logs counts only — never a name or a text.
"""
import logging
from collections import Counter

from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_sports_clinic.models.medical_alerts import suggest_medical_items

_logger = logging.getLogger(__name__)

CTX = {'sc_phone_lenient': True, 'sc_critical_quiet': True, 'tracking_disable': True,
       'mail_notrack': True, 'mail_create_nosubscribe': True, 'dashboard_bump': True,
       'active_test': False}
FAMILIES = (
    ('allergy', 'allergy_level', 'allergy_details', 'allergy_none_confirmed'),
    ('medical_alert', 'medical_alert_level', 'medical_alert_details', 'medical_none_confirmed'),
)


def _old_levels(cr):
    """The stored levels as the previous version left them (the column is
    computed now, not yet recomputed)."""
    cr.execute("SELECT id, allergy_level, medical_alert_level FROM sports_patient")
    return {row[0]: {'allergy': row[1], 'medical_alert': row[2]} for row in cr.fetchall()}


def _family_items(suggestion, family, own_text):
    items = list(suggestion[family])
    if not items and own_text:
        # A family's own details whose segments all read as the other family
        # (« Ventolin » typed in the allergies): they stay in this family.
        other = 'medical_alert' if family == 'allergy' else 'allergy'
        items = list(suggestion[other])
    return items


def convert(env):
    env = env(context=dict(env.context, **CTX))
    Patient = env['sports.patient'].sudo()
    Item = env['sports.patient.critical.item'].sudo()
    counts = Counter()
    old_levels = _old_levels(env.cr)
    players = Patient.search([])
    existing = {}
    for item in Item.search([('patient_id', 'in', players.ids)]):
        existing.setdefault((item.patient_id.id, item.family), 0)
        existing[(item.patient_id.id, item.family)] += 1
    to_create = []
    for player in players:
        levels = old_levels.get(player.id, {})
        has_any = any(levels.values()) or player.allergy_details or player.medical_alert_details or any(
            (player.id, family) in existing for family, *_rest in FAMILIES)
        legacy = (player.allergies or '').strip() if not has_any else ''
        legacy_suggestion = suggest_medical_items(legacy) if legacy else None
        vals = {}
        flagged = False
        for family, _level_field, details_field, none_field in FAMILIES:
            old_level = levels.get(family)
            if (player.id, family) in existing:
                counts['%s_kept_items' % family] += 1
                continue
            own = (player[details_field] or '').strip()
            if own:
                suggestion = suggest_medical_items(own)
                items = _family_items(suggestion, family, own)
                epipen = suggestion['epipen']
            elif legacy_suggestion:
                suggestion = legacy_suggestion
                items = list(suggestion[family])
                epipen = suggestion['epipen']
            else:
                suggestion, items, epipen = None, [], False
            if items:
                if old_level == 'minor':
                    # The clinic chose « Not urgent »: no life-threatening item.
                    items = [dict(item, life_threatening=False) for item in items]
                elif old_level == 'urgent' and not any(item['life_threatening'] for item in items):
                    items = [dict(item, life_threatening=True) for item in items]
                to_create.extend(dict(item, patient_id=player.id, family=family, sequence=10 + n)
                                 for n, item in enumerate(items))
                counts['%s_players_from_text' % family] += 1
                counts['%s_items' % family] += len(items)
                counts['%s_items_vital' % family] += sum(1 for item in items if item['life_threatening'])
                if family == 'allergy' and epipen and not player.allergy_epipen:
                    vals['allergy_epipen'] = True
                    counts['epipen_from_text'] += 1
                flagged = True
                continue
            if old_level == 'none' or (suggestion and suggestion['kind'] == 'none'):
                if not player[none_field]:
                    vals[none_field] = True
                counts['%s_none_confirmed' % family] += 1
            elif own:
                # Text that made no item (only cue words): left to validate.
                flagged = True
                counts['%s_text_without_item' % family] += 1
        if flagged and not player.medical_alert_review:
            vals['medical_alert_review'] = True
            counts['newly_flagged'] += 1
        if vals:
            player.write(vals)
    if to_create:
        Item.create(to_create)
    # The levels: computed from now on, recomputed once for everyone.
    for name in ('allergy_level', 'medical_alert_level'):
        env.add_to_compute(Patient._fields[name], players)
    env.flush_all()
    counts['scanned'] = len(players)
    for family, level_field, *_rest in FAMILIES:
        env.cr.execute("SELECT %s, COUNT(*) FROM sports_patient GROUP BY 1" % level_field)  # noqa: S608 (constant)
        for level, count in env.cr.fetchall():
            counts['%s_level_%s' % (family, level or 'unset')] = count
    return counts


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP TABLE IF EXISTS sports_patient_medical_undo CASCADE")
    counts = convert(api.Environment(cr, SUPERUSER_ID, {}))
    _logger.info("Task 1677 structured medical lists: %s",
                 ", ".join("%s=%s" % (key, counts[key]) for key in sorted(counts)))
