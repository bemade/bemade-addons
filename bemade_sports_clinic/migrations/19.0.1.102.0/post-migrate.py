"""Task 1645 — one-time reformat of the clinic's phone numbers.

Valid numbers that are not in the clinic format yet (+1 514-555-0123) are
rewritten; unparseable ones are left untouched (MC finds them with the
« Phone numbers to fix » filter on players). Players' and staff phones live on
their partner; emergency contacts carry their own mobile. Idempotent: a
second run finds everything already formatted. Logs counts only — never a
number.
"""
import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.bemade_sports_clinic.models.sc_phone import sc_normalize_phone, sc_phone_is_valid

_logger = logging.getLogger(__name__)

CTX = {
    'sc_phone_lenient': True,
    'tracking_disable': True,
    'mail_notrack': True,
    'mail_create_nolog': True,
}


def _reformat(env, records, field, country_of):
    counts = {'reformatted': 0, 'already_ok': 0, 'invalid': 0}
    for record in records:
        value = record[field]
        if not value:
            continue
        country = country_of(record)
        if not sc_phone_is_valid(env, value, country):
            counts['invalid'] += 1
            continue
        formatted = sc_normalize_phone(env, value, country=country, strict=False)
        if formatted == value:
            counts['already_ok'] += 1
        else:
            record.write({field: formatted})
            counts['reformatted'] += 1
    return counts


def reformat_phones(env):
    env = env(context=dict(env.context, **CTX))
    company_country = env.company.country_id
    patients = env['sports.patient'].with_context(active_test=False).search([])
    staff = env['sports.team.staff'].with_context(active_test=False).search([])
    partners = (patients.mapped('partner_id') | staff.mapped('partner_id')).with_context(active_test=False)
    results = {
        'partners (players + staff)': _reformat(
            env, partners, 'phone', lambda p: p.country_id or company_country),
        'emergency contacts': _reformat(
            env, env['sports.patient.contact'].search([]), 'mobile',
            lambda c: c.patient_id.country_id or company_country),
    }
    for label, counts in results.items():
        _logger.info(
            "Task 1645 phone reformat — %s: reformatted=%d already_ok=%d invalid_left=%d",
            label, counts['reformatted'], counts['already_ok'], counts['invalid'])
    return results


def migrate(cr, version):
    if not version:
        return
    reformat_phones(api.Environment(cr, SUPERUSER_ID, {}))
