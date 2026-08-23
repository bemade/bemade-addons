import logging

from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Task 1415: backfill ``sports.team.staff.source``.

    The column is created by the ORM with the field default (``manual``) for
    every existing row; rows that #539's event coverage created
    (``is_auto_created``) are event rows. ``is_auto_created`` itself is kept
    as-is (the event cleanup cron still filters on it). Idempotent: only rows
    still at ``manual`` with the auto flag are touched; counts are logged so
    the upgrade log shows what moved.
    """
    if not column_exists(cr, "sports_team_staff", "source"):
        _logger.warning("Task 1415: sports_team_staff.source missing — nothing to backfill")
        return
    cr.execute("UPDATE sports_team_staff SET source = 'manual' WHERE source IS NULL")
    cr.execute(
        """
        UPDATE sports_team_staff
           SET source = 'event'
         WHERE is_auto_created IS TRUE
           AND source = 'manual'
        """
    )
    moved = cr.rowcount
    cr.execute("SELECT source, count(*) FROM sports_team_staff GROUP BY source ORDER BY source")
    _logger.info(
        "Task 1415: source backfilled — %s row(s) moved to 'event'; totals: %s",
        moved,
        ", ".join("%s=%s" % row for row in cr.fetchall()),
    )
