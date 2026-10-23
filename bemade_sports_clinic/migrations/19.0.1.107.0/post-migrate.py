"""Task 1654 — the players already « Urgent » get SUGGESTED critical items.

For each family (allergies, medical alert) at « Urgent – life-threatening »
with no critical item yet: the rule-based suggester
(``suggest_critical_items``) splits the details and keeps the segments with an
urgent cue (EpiPen, sévère / severe, anaphyla*, mortel, choc…), else the whole
text; one item per segment (EpiPen when the segment says so, or when the player
had EpiPen and there is only one). The player is flagged « to validate »
(medical_alert_review) for MC. Nothing else changes. Idempotent (a family
with items is skipped); logs counts only — never a name.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_sports_clinic.models.patient_critical_item import suggest_critical_items

_logger = logging.getLogger(__name__)

CTX = {'sc_phone_lenient': True, 'sc_critical_quiet': True, 'tracking_disable': True,
       'mail_notrack': True, 'active_test': False}


def convert_urgent_players(env):
    env = env(context=dict(env.context, **CTX))
    Item = env['sports.patient.critical.item']
    counts = {'allergy': 0, 'medical_alert': 0, 'items': 0, 'players_flagged': 0, 'no_text': 0}
    specs = (('allergy', 'allergy_level', 'allergy_details', 'allergy_epipen'),
             ('medical_alert', 'medical_alert_level', 'medical_alert_details', None))
    flagged = env['sports.patient']
    for family, level_field, details_field, epipen_field in specs:
        players = env['sports.patient'].search([(level_field, '=', 'urgent')])
        existing = set(Item.search([('patient_id', 'in', players.ids), ('family', '=', family)]).mapped('patient_id').ids)
        for player in players:
            if player.id in existing:
                continue
            suggestions = suggest_critical_items(
                family, player[details_field], epipen=bool(epipen_field and player[epipen_field]))
            if not suggestions:
                counts['no_text'] += 1
                flagged |= player
                continue
            Item.create([dict(item, patient_id=player.id, family=family) for item in suggestions])
            counts[family] += 1
            counts['items'] += len(suggestions)
            flagged |= player
    flagged = flagged.filtered(lambda p: not p.medical_alert_review)
    if flagged:
        flagged.write({'medical_alert_review': True})
    counts['players_flagged'] = len(flagged)
    _logger.info(
        "Task 1654 critical items: allergy players=%d medical-alert players=%d items=%d "
        "urgent without text=%d newly flagged to validate=%d",
        counts['allergy'], counts['medical_alert'], counts['items'], counts['no_text'],
        counts['players_flagged'])
    return counts


def migrate(cr, version):
    if not version:
        return
    convert_urgent_players(api.Environment(cr, SUPERUSER_ID, {}))
