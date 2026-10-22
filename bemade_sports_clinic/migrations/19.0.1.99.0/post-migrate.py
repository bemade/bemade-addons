"""Task 1630 — allergies + medical alerts replace the free-text allergies.

One-time conversion of the legacy ``allergies`` text (kept as a hidden
column) into the new fields, by predicate — never by ids, the repository is
public. The classification rules and keyword lists live in code
(``models/medical_alerts.py``, ``classify_legacy_allergies``):

* « aucune » and its variants -> allergy level « None », details empty;
* empty -> nothing set (« Not specified »);
* real text -> pre-filled (condition words -> medical alert, otherwise
  allergies; EpiPen / « sévère » -> urgent, the EpiPen box ticked unless
  « no / pas d'EpiPen »), the original text verbatim in the details, and
  flagged « To validate » for the clinic's back-end list.

Idempotent: a player with either level already set is skipped. Logs counts
only (no names, no text).
"""
import logging
from collections import Counter

from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_sports_clinic.models.medical_alerts import (
    LEVEL_URGENT,
    classify_legacy_allergies,
)

_logger = logging.getLogger(__name__)

QUIET = {
    'tracking_disable': True,
    'mail_notrack': True,
    'mail_create_nosubscribe': True,
    'dashboard_bump': True,
}


def convert(env):
    """Convert every player whose levels are both unset. Returns the counts."""
    Patient = env['sports.patient'].sudo().with_context(active_test=False, **QUIET)
    players = Patient.search([
        ('allergy_level', '=', False),
        ('medical_alert_level', '=', False),
    ])
    counts = Counter()
    none_ids = []
    for player in players:
        vals = classify_legacy_allergies(player.allergies)
        kind = vals.pop('kind')
        counts[kind] += 1
        if kind == 'empty':
            continue
        if kind == 'none':
            none_ids.append(player.id)
            continue
        if vals.get('allergy_level'):
            counts['prefilled_allergy'] += 1
            if vals['allergy_level'] == LEVEL_URGENT:
                counts['allergy_urgent'] += 1
        if vals.get('medical_alert_level'):
            counts['prefilled_medical_alert'] += 1
            if vals['medical_alert_level'] == LEVEL_URGENT:
                counts['medical_alert_urgent'] += 1
        if vals.get('allergy_epipen'):
            counts['epipen'] += 1
        if vals.get('medical_alert_review'):
            counts['review'] += 1
        player.write(vals)
    if none_ids:
        # Owner review 2026-10-21: « aucune » = nothing to report on both.
        Patient.browse(none_ids).write({'allergy_level': 'none', 'allergy_details': False,
                                        'medical_alert_level': 'none', 'medical_alert_details': False})
    counts['scanned'] = len(players)
    return counts


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    counts = convert(env)
    _logger.info(
        "Task 1630: allergies converted — scanned %s players: %s « none » (allergy level None), "
        "%s empty (Not specified), %s pre-filled (%s allergies, %s medical alerts, "
        "%s allergy urgent, %s medical alert urgent, %s EpiPen, %s flagged to validate).",
        counts['scanned'], counts['none'], counts['empty'], counts['prefilled'],
        counts['prefilled_allergy'], counts['prefilled_medical_alert'],
        counts['allergy_urgent'], counts['medical_alert_urgent'], counts['epipen'],
        counts['review'])
