import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill the Law 25 retention clock for teamless players.

    Until this version the retention clock (``date_left_last_team``) was
    maintained on the patient side only, so every team-side path — the per-row
    "x" on the Players tab, a team-side write, a team deletion — could leave a
    player teamless with a NULL clock. A NULL clock never surfaces to the Law 25
    retention rule, so those records would never be reviewed for anonymization.
    Stamp today's date on every teamless player whose clock is unset.

    This migration does NOT archive anyone and does NOT touch roster rows.
    Auto-archiving teamless players was considered and dropped (owner,
    2026-07-16): most teamless players are simply between seasons awaiting
    re-rostering, not departed. Archiving stays a manual action.

    Same sanity rule as the original 19.0.1.5.3 backfill: we cannot know when
    these players actually left, so their retention clock starts today.

    Raw SQL posts no chatter, so this is silent by design — the row count is
    logged instead.
    """
    cr.execute(
        """
        UPDATE sports_patient p
           SET date_left_last_team = CURRENT_DATE
         WHERE p.date_left_last_team IS NULL
           AND NOT EXISTS (
               SELECT 1 FROM sports_team_patient_rel r
                WHERE r.patient_id = p.id
           )
        """
    )
    _logger.info(
        "Roster heal (Law 25 clock): stamped date_left_last_team on %s "
        "teamless players; archived none",
        cr.rowcount,
    )
