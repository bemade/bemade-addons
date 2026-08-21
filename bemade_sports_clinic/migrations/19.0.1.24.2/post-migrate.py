import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Purge essentially-empty injury note history rows (task 1404).

    The pre-1404 capture compared old/new note values raw, so clears and
    whitespace-only writes created blank ``sports.injury.note.history`` rows.
    The capture is now strip-normalized (essentially-empty new values log
    nothing — a customer decision, clears included), and this migration
    deletes the blank rows already recorded. Plain data delete via SQL: the
    model is append-only by policy, so the cleanup belongs here rather than
    in a UI unlink. Raw SQL posts no chatter, so the row count is logged.
    """
    cr.execute(
        """
        DELETE FROM sports_injury_note_history
         WHERE content IS NULL OR btrim(content) = ''
        """
    )
    _logger.info(
        "Task 1404: deleted %s essentially-empty injury note history rows",
        cr.rowcount,
    )
