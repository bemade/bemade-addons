"""Task 1416 — informational migration note.

The event-coverage access (task 539) now opens only at coverage start minus the
lead (Settings, default 48 h). Existing event-coverage staff rows whose event
starts further ahead than the lead are CLOSED by the first hourly reconcile
(``sports.team.staff._reconcile_timed_rows``) — accepted by the owner ("too
early" access is the bug). Nothing is changed here: this script only logs how
many rows that is, so the upgrade log carries the number.
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT COUNT(DISTINCT s.id)
          FROM sports_team_staff s
          JOIN sports_team_staff_event_rel rel ON rel.staff_id = s.id
          JOIN sports_event e ON e.id = rel.event_id
         WHERE s.source = 'event'
           AND e.state != 'cancelled'
           AND COALESCE(e.therapist_start, e.date_start)
               > (now() at time zone 'UTC') + interval '48 hours'
           AND NOT EXISTS (
               SELECT 1 FROM sports_team_staff_event_rel r2
                 JOIN sports_event e2 ON e2.id = r2.event_id
                WHERE r2.staff_id = s.id AND e2.state != 'cancelled'
                  AND COALESCE(e2.therapist_start, e2.date_start)
                      <= (now() at time zone 'UTC') + interval '48 hours'
                  AND COALESCE(e2.therapist_end, e2.date_end)
                      >= (now() at time zone 'UTC')
           )
        """
    )
    too_early = cr.fetchone()[0]
    cr.execute("SELECT COUNT(*) FROM sports_team_staff WHERE source = 'event'")
    total = cr.fetchone()[0]
    _logger.info(
        "Task 1416: %s of %s event-coverage staff row(s) belong only to events "
        "starting more than 48 h ahead — the first hourly reconcile closes them "
        "(access reopens 48 h before the coverage).",
        too_early, total,
    )
