import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Heal the roster states the pre-19.0.1.7.0 code could produce.

    Until this version the roster invariants were enforced on the patient side
    only, so every team-side path could break them. Three strays are possible and
    all three are healed here:

      I3  archived ⇒ not rostered      -- (a)
      I1  teamless ⇔ retention clock   -- (b)
      I2  teamless ⇒ archived          -- (c)

    THE ORDER IS LOAD-BEARING. (a) drops the roster rows of archived players,
    which is what makes them teamless; only then can (b) stamp their clock and
    (c) settle the rest. Run (c) first and it misses the players (a) is about to
    make teamless; run (b) before (a) and those players keep a NULL clock
    forever — and a NULL clock never surfaces to the Law 25 retention rule, so
    the record is never anonymized. That silent no-op is the bug being fixed.

    Same sanity rule as the original 19.0.1.5.3 backfill: we cannot know when
    these players actually left, so their retention clock starts today.

    Raw SQL posts no chatter, so this is silent by design — every row count is
    logged instead.
    """
    # (a) I3 -- archived players are not on any roster.
    cr.execute(
        """
        DELETE FROM sports_team_patient_rel r
              USING sports_patient p
              WHERE r.patient_id = p.id
                AND p.active = false
        """
    )
    _logger.info(
        "Roster heal (I3): dropped %s roster rows belonging to archived players",
        cr.rowcount,
    )

    # (b) I1 -- teamless players carry a retention clock. Re-run of the
    #     19.0.1.5.3 backfill: it is the players (a) just orphaned that need it.
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
        "Roster heal (I1): stamped date_left_last_team on %s teamless players",
        cr.rowcount,
    )

    # (c) I2 -- teamless players are archived. These are the players the
    #     never-registered archiving cron was supposed to have swept.
    cr.execute(
        """
        UPDATE sports_patient p
           SET active = false
         WHERE p.active
           AND NOT EXISTS (
               SELECT 1 FROM sports_team_patient_rel r
                WHERE r.patient_id = p.id
           )
        """
    )
    _logger.info(
        "Roster heal (I2): archived %s players left without a team",
        cr.rowcount,
    )
