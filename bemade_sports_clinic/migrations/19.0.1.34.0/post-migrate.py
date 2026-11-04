import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)

# Must match security/sports_clinic_attendance_rules.xml.
PORTAL_TP_RULE_DOMAIN = (
    "['|', ('patient_id.team_ids.staff_ids.user_ids', 'in', user.id), "
    "'&', ('patient_id', '=', False), ('event_id.assigned_staff_ids', 'in', user.id)]"
)


def migrate(cr, version):
    """Task 1418: unregistered kiosk sign-ins on the clinic worklist.

    * ``sports.clinic.attendance.patient_id`` is no longer required. The ORM
      drops the NOT NULL itself during the update; verified (and repaired if
      need be) here so the upgrade log shows it.
    * The portal-TP record rule gains the unregistered branch. The XML is a
      plain <data> block, but an ir.rule that was ever frozen (noupdate) would
      keep the old domain and hide every unregistered row from the ORM — so
      the domain is re-applied here unconditionally. Idempotent.
    """
    if column_exists(cr, 'sports_clinic_attendance', 'patient_id'):
        cr.execute("""
            SELECT is_nullable FROM information_schema.columns
             WHERE table_name = 'sports_clinic_attendance' AND column_name = 'patient_id'
        """)
        nullable = (cr.fetchone() or ['NO'])[0] == 'YES'
        if not nullable:
            _logger.info("Task 1418: dropping NOT NULL on sports_clinic_attendance.patient_id")
            cr.execute("ALTER TABLE sports_clinic_attendance ALTER COLUMN patient_id DROP NOT NULL")
        else:
            _logger.info("Task 1418: sports_clinic_attendance.patient_id already nullable")

    env = api.Environment(cr, SUPERUSER_ID, {})
    rule = env.ref('bemade_sports_clinic.portal_tp_clinic_attendance_rule',
                   raise_if_not_found=False)
    if not rule:
        _logger.warning("Task 1418: portal_tp_clinic_attendance_rule not found — nothing to re-apply")
        return
    if rule.domain_force != PORTAL_TP_RULE_DOMAIN:
        rule.write({'domain_force': PORTAL_TP_RULE_DOMAIN})
        _logger.info("Task 1418: portal_tp_clinic_attendance_rule domain re-applied (rule %s)", rule.id)
    else:
        _logger.info("Task 1418: portal_tp_clinic_attendance_rule domain already current (rule %s)", rule.id)
