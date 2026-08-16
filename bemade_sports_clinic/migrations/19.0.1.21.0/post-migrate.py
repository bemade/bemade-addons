import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Flip existing teams to show the player position on their dashboard.

    Task 1390: the ``show_position_on_dashboard`` per-team toggle default
    changed from False to True. A default change alone only affects newly
    created records, so existing teams keep whatever value the column already
    holds (all incidental False on staging; brand-new column on prod). This
    data migration re-asserts True on every team whose value is not already
    True so both surfaces end up consistent with the new default.

    The field stays per-team toggleable: a team can still be set back to False
    after the upgrade. Raw SQL posts no chatter, so the row count is logged.
    """
    cr.execute(
        """
        UPDATE sports_team
           SET show_position_on_dashboard = TRUE
         WHERE show_position_on_dashboard IS DISTINCT FROM TRUE
        """
    )
    _logger.info(
        "Task 1390: set show_position_on_dashboard = TRUE on %s teams",
        cr.rowcount,
    )
