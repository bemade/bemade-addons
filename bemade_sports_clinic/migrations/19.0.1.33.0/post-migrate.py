import logging

from odoo.tools.sql import column_exists, table_exists

_logger = logging.getLogger(__name__)


def _count(cr, query):
    cr.execute(query)
    return cr.fetchone()[0]


def migrate(cr, version):
    """Task 1240: ``sports.patient.injury`` lost ``treatment_professional_ids``
    (m2m res.users), ``team_id`` (m2o sports.team) and the non-stored
    ``allowed_team_ids`` helper. Team staff is the treater list; access,
    followers and the subtype split are group/team-staff based.

    Odoo drops the ``team_id`` column itself when the ``ir.model.fields`` row
    goes at the end of the update (and its ``mail.tracking.value`` rows
    cascade — accepted), but a non-manual m2m relation table is left on disk.
    This migration removes the relation table and the column explicitly, so
    the schema is clean regardless of ordering. Idempotent: every statement
    is ``IF EXISTS``; the row counts are logged before dropping so the upgrade
    log shows what went. Chatter message bodies are untouched.
    """
    if table_exists(cr, 'patient_injury_treatment_pro_rel'):
        n = _count(cr, "SELECT count(*) FROM patient_injury_treatment_pro_rel")
        _logger.info("Task 1240: dropping patient_injury_treatment_pro_rel (%s row(s))", n)
    else:
        _logger.info("Task 1240: patient_injury_treatment_pro_rel already gone")
    cr.execute("DROP TABLE IF EXISTS patient_injury_treatment_pro_rel")

    if column_exists(cr, 'sports_patient_injury', 'team_id'):
        n = _count(cr, "SELECT count(*) FROM sports_patient_injury WHERE team_id IS NOT NULL")
        _logger.info("Task 1240: dropping sports_patient_injury.team_id (%s non-null value(s))", n)
    else:
        _logger.info("Task 1240: sports_patient_injury.team_id already gone")
    cr.execute("ALTER TABLE sports_patient_injury DROP COLUMN IF EXISTS team_id")

    # allowed_team_ids was a non-stored compute: no table is expected, but a
    # stray one (older builds) must not survive either.
    cr.execute("DROP TABLE IF EXISTS sports_patient_injury_allowed_team_rel")
