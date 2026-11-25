# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""19.0.1.8.1: practice dates are the learner's (his time zone), whoever ran the code.

* ``unit_access.unlocked_on``: a unit unlocked in the evening from a caller with no time
  zone got the UTC date (tomorrow). Moved to the learner's local date of the row's
  ``create_date`` **only** where ``unlocked_on`` is the UTC date of ``create_date`` and the
  local date differs — the rows the bug produced. Other rows are left alone.
* ``xp.day``: recomputed only for the rows whose stored day is not the learner's local date
  of their ``date`` (logged; append-only rows, so plain SQL).
Idempotent.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Student = env["homeschool.student"].with_context(active_test=False)

    cr.execute("""
        SELECT id, student_id, create_date, unlocked_on
          FROM homeschool_practice_unit_access
         WHERE unlocked_on IS NOT NULL AND unlocked_on = create_date::date
    """)
    fixed = 0
    for row_id, student_id, created, unlocked in cr.fetchall():
        local = Student.browse(student_id)._practice_local_date(created)
        if local and local != unlocked:
            cr.execute("UPDATE homeschool_practice_unit_access SET unlocked_on = %s WHERE id = %s", (local, row_id))
            fixed += 1
    _logger.info("homeschool_practice 19.0.1.8.1: %d unit unlock date(s) moved to the learner's day", fixed)

    cr.execute("SELECT id, student_id, date, day FROM homeschool_practice_xp WHERE date IS NOT NULL")
    xp = 0
    for row_id, student_id, moment, day in cr.fetchall():
        local = Student.browse(student_id)._practice_local_date(moment)
        if local != day:
            cr.execute("UPDATE homeschool_practice_xp SET day = %s WHERE id = %s", (local, row_id))
            xp += 1
    _logger.info("homeschool_practice 19.0.1.8.1: %d XP day(s) recomputed", xp)
    if fixed or xp:
        env.invalidate_all()
