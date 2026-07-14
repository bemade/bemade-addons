import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Law 25 retention-clock backfill (owner 2026-07-12).

    ``date_left_last_team`` is introduced in this version. For players who were
    ALREADY teamless when it landed we cannot know when they actually left, so
    stamp it to today — their retention clock starts now (the sanity rule).
    Players still on a team keep it NULL (set later, on the write that removes
    their last team).
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
    _logger.info("Law 25 backfill: stamped date_left_last_team on %s teamless players", cr.rowcount)
