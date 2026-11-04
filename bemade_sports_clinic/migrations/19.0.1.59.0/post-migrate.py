"""Task 1589 — coaches see only their own activities.

The coach record rule on mail.activity
(``bemade_sports_clinic.mail_activity_portal_team_coach_rule``) now limits a
portal coach to the activities assigned to them OR created by them, still
within their team scope. The XML reload updates the rule on a normal
upgrade; this script applies the same domain when the rule's xmlid is
``noupdate`` on a database (or was edited by hand), so every database ends
up with the new rule. Idempotent; logs what it changed.

Keep ``COACH_DOMAIN`` identical to ``security/mail_activity_portal_rules.xml``
(a test compares them).
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

RULE_XMLID = 'bemade_sports_clinic.mail_activity_portal_team_coach_rule'

COACH_DOMAIN = """[
    '&',
    '|', ('user_id', '=', user.id), ('create_uid', '=', user.id),
    '|', '|', '|',
    '&', '&',
    ('res_model', '=', 'sports.patient'),
    ('res_id', '!=', False),
    ('res_id', 'in', user.partner_id.team_staff_rel_ids.mapped('team_id.patient_ids.id') or [0]),
    '&', '&',
    ('res_model', '=', 'sports.patient.injury'),
    ('res_id', '!=', False),
    ('res_id', 'in', user.partner_id.team_staff_rel_ids.mapped('team_id.patient_ids.injury_ids.id') or [0]),
    '&', '&',
    ('res_model', '=', 'sports.team'),
    ('res_id', '!=', False),
    ('res_id', 'in', user.partner_id.team_staff_rel_ids.mapped('team_id.id') or [0]),
    '&', '&',
    ('res_model', '=', 'sports.event'),
    ('res_id', '!=', False),
    ('res_id', 'in', user.partner_id.team_staff_rel_ids.mapped('team_id.event_ids.id') or [0])
]"""


def _normalized(domain):
    return ''.join((domain or '').split())


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref(RULE_XMLID, raise_if_not_found=False)
    if not rule:
        _logger.warning("Task 1589: %s not found — nothing to migrate.", RULE_XMLID)
        return
    vals = {}
    if _normalized(rule.domain_force) != _normalized(COACH_DOMAIN):
        vals['domain_force'] = COACH_DOMAIN
    # Permissions unchanged by task 1589 (read only); re-asserted in case a
    # database drifted.
    for perm, expected in (('perm_read', True), ('perm_write', False),
                           ('perm_create', False), ('perm_unlink', False)):
        if rule[perm] != expected:
            vals[perm] = expected
    if vals:
        rule.write(vals)
        _logger.info("Task 1589: coach mail.activity rule %s updated (%s).",
                     rule.id, ', '.join(sorted(vals)))
    else:
        _logger.info("Task 1589: coach mail.activity rule %s already up to date.", rule.id)
