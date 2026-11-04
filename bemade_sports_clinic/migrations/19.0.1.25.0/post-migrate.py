import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Backfill the per-team "last player activity" stamps (task 1401).

    The two new sports.team columns are maintained incrementally from now on
    (sports.patient._bump_dashboard_activity pushes every new stamp to the
    player's teams), so existing teams would otherwise all start NULL and the
    portal /my/teams "recent activity" order would be flat until activity
    happens. Seed each team with the MAX of its current players' role-scoped
    dashboard_last_activity_<role> stamps — the exact value incremental
    maintenance would have produced. Teams whose players have no recorded
    activity stay NULL and sort last.

    Raw SQL posts no chatter, so the row counts are logged.
    """
    for role in ("coach", "tp"):
        cr.execute(
            """
            UPDATE sports_team AS t
               SET last_player_activity_%(role)s_at = s.last_at
              FROM (
                       SELECT rel.team_id,
                              MAX(p.dashboard_last_activity_%(role)s) AS last_at
                         FROM sports_team_patient_rel AS rel
                         JOIN sports_patient AS p ON p.id = rel.patient_id
                        GROUP BY rel.team_id
                   ) AS s
             WHERE s.team_id = t.id
               AND s.last_at IS NOT NULL
               AND (t.last_player_activity_%(role)s_at IS NULL
                    OR t.last_player_activity_%(role)s_at < s.last_at)
            """
            % {"role": role}
        )
        _logger.info(
            "Task 1401: backfilled last_player_activity_%s_at on %s teams",
            role,
            cr.rowcount,
        )
