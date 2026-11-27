"""Backfill the dates of open FSM subtasks (durpro task 1062).

Subtasks created or attached under an already-scheduled visit used to get no
dates, so they were missing from Planning. Give every OPEN FSM subtask without a
start date the start date and deadline of its nearest scheduled ancestor (the
closest task up the parent chain with both dates set). Done and cancelled
subtasks are left alone. Plain SQL: no ORM write cascade, no chatter.
"""

import logging

_logger = logging.getLogger(__name__)

BACKFILL_SQL = """
WITH RECURSIVE chain AS (
    SELECT t.id AS task_id, t.parent_id AS ancestor_id, 1 AS depth
      FROM project_task t
      JOIN project_project p ON p.id = t.project_id
     WHERE t.parent_id IS NOT NULL
       AND p.is_fsm
       AND t.active
       AND t.state NOT IN ('1_done', '1_canceled')
       AND t.planned_date_begin IS NULL
    UNION ALL
    SELECT c.task_id, a.parent_id, c.depth + 1
      FROM chain c
      JOIN project_task a ON a.id = c.ancestor_id
     WHERE a.parent_id IS NOT NULL
       AND (a.planned_date_begin IS NULL OR a.date_deadline IS NULL)
),
nearest AS (
    SELECT DISTINCT ON (c.task_id)
           c.task_id, a.planned_date_begin, a.date_deadline
      FROM chain c
      JOIN project_task a ON a.id = c.ancestor_id
     WHERE a.planned_date_begin IS NOT NULL
       AND a.date_deadline IS NOT NULL
     ORDER BY c.task_id, c.depth
)
UPDATE project_task t
   SET planned_date_begin = n.planned_date_begin,
       date_deadline = n.date_deadline
  FROM nearest n
 WHERE t.id = n.task_id
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute(BACKFILL_SQL)
    _logger.info(
        "bemade_fsm: %s open FSM subtask(s) took the dates of their nearest "
        "scheduled ancestor",
        cr.rowcount,
    )
