"""Task 1677 — the #1654 critical items become structured list items.

Before the module loads (its new fields would otherwise be created empty):

* ``action`` (« What to do ») is renamed ``first_aid_note``;
* ``life_threatening`` is added, TRUE for every existing item (a #1654 item
  was by definition life-threatening);
* an item's EpiPen moves to the player (``allergy_epipen`` OR'ed; the old
  ``epipen`` column is left in place, unused).

Idempotent (each step checks the columns first); logs counts only.
"""
import logging

_logger = logging.getLogger(__name__)

TABLE = 'sports_patient_critical_item'


def _columns(cr, table):
    cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
    return {row[0] for row in cr.fetchall()}


def migrate(cr, version):
    if not version:
        return
    columns = _columns(cr, TABLE)
    if not columns:
        return
    renamed = vital = epipen = 0
    if 'action' in columns and 'first_aid_note' not in columns:
        cr.execute('ALTER TABLE %s RENAME COLUMN action TO first_aid_note' % TABLE)
        renamed = 1
    if 'life_threatening' not in columns:
        cr.execute('ALTER TABLE %s ADD COLUMN life_threatening BOOLEAN' % TABLE)
        cr.execute('UPDATE %s SET life_threatening = TRUE' % TABLE)
        vital = cr.rowcount
    if 'epipen' in columns:
        cr.execute("""
            UPDATE sports_patient p
               SET allergy_epipen = TRUE
             WHERE COALESCE(p.allergy_epipen, FALSE) = FALSE
               AND EXISTS (SELECT 1 FROM sports_patient_critical_item i
                            WHERE i.patient_id = p.id AND i.family = 'allergy' AND i.epipen)
        """)
        epipen = cr.rowcount
    _logger.info(
        "Task 1677 pre-migrate: action->first_aid_note renamed=%d, items marked life-threatening=%d, "
        "players given EpiPen from their items=%d", renamed, vital, epipen)
