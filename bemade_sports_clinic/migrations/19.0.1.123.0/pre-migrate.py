"""Task 1717 — EpiPen becomes a Yes / No answer (empty = not provided).

Owner decision 2026-10-26: every EXISTING player keeps an answer — the old
boolean True becomes « yes », False (or NULL) becomes « no »; no existing
player becomes empty (only new players start unanswered). The column is
created here, before the ORM loads, so the boolean (now a stored compute of
it) holds the very same values. On a database older than #1630 (no boolean
column yet — prod at 19.0.1.42.x) nothing happens here: the post-migrate
fills the answers once the earlier migrations have set the boolean.
Idempotent: only rows without an answer are filled; logs the counts.
"""
import logging

_logger = logging.getLogger(__name__)


def _has_column(cr, table, column):
    cr.execute("SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
               (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    """Also called by the post-migrate (``fill_answers``)."""
    if not _has_column(cr, 'sports_patient', 'allergy_epipen'):
        # An older database (the boolean comes with #1630, 19.0.1.99.0): the
        # ORM creates both columns, the earlier post-migrates set the
        # boolean, and THIS version's post-migrate fills the answers.
        _logger.info("1717 EpiPen answer: no allergy_epipen column yet — the post-migrate fills it")
        return
    fill_answers(cr)


def fill_answers(cr):
    cr.execute("ALTER TABLE sports_patient ADD COLUMN IF NOT EXISTS allergy_epipen_state varchar")
    cr.execute("""
        SELECT COUNT(*) FILTER (WHERE allergy_epipen),
               COUNT(*) FILTER (WHERE NOT COALESCE(allergy_epipen, FALSE)),
               COUNT(*)
          FROM sports_patient""")
    before_yes, before_no, total = cr.fetchone()
    cr.execute("""
        UPDATE sports_patient
           SET allergy_epipen_state = CASE WHEN allergy_epipen THEN 'yes' ELSE 'no' END
         WHERE allergy_epipen_state IS NULL""")
    filled = cr.rowcount
    cr.execute("""
        SELECT COUNT(*) FILTER (WHERE allergy_epipen_state = 'yes'),
               COUNT(*) FILTER (WHERE allergy_epipen_state = 'no'),
               COUNT(*) FILTER (WHERE allergy_epipen_state IS NULL)
          FROM sports_patient""")
    after_yes, after_no, after_empty = cr.fetchone()
    _logger.info(
        "1717 EpiPen answer: %d players (archived included); boolean yes=%d no=%d -> "
        "state yes=%d no=%d empty=%d (%d filled)",
        total, before_yes, before_no, after_yes, after_no, after_empty, filled)
