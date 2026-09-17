# -*- coding: utf-8 -*-
"""UC-02 — Blocks are the unit of planning; the day is a container.

Acceptance criteria
-------------------
1. A ``homeschool.day`` has a date, a student, ``start_time`` (default 09:00), opening
   plan, "evening before" checklist, debrief and note (Markdown), and ordered blocks.
2. A ``homeschool.block`` has ``day_id``, ``sequence``, ``kind`` (opening | bloc | pause |
   reading | projects | ressource | debrief | bonus), ``subject_id``, ``name``,
   ``duration_planned`` (minutes), Markdown fields intention / steps / success / fallback,
   ``item_ids``, ``material_ids``, ``project_id``, ``trace_ids``.
3. ``start_time`` is **computed and stored**: the first block starts at the day's start;
   each block starts when the previous one ends; pauses count like any block.
4. A block with ``start_fixed`` set (reading at 14:00) starts there and the computation
   resumes from it; a fixed time earlier than the previous block's end raises a
   ValidationError.
5. Reordering (changing ``sequence``) recomputes every start time of the day.
6. Moving a block to another day (writing ``day_id``) recomputes both days, sets
   ``status = moved`` on nothing (the block just moves) and the chatter records the
   old and new day (tracking on ``day_id`` and ``sequence``).
7. ``end_time`` and the day's ``planned_minutes`` / ``end_time`` are computed sums.
8. Kanban grouped by ``day_id`` and calendar view on ``start_datetime`` /
   ``duration_planned`` exist (view smoke test).
"""
from .common import HomeschoolCase


class TestBlocksAndDays(HomeschoolCase):
    def test_start_times_follow_sequence(self):
        self.skipTest("pending — TDD")

    def test_pause_is_a_block(self):
        self.skipTest("pending — TDD")

    def test_anchored_block(self):
        self.skipTest("pending — TDD")

    def test_anchor_before_previous_end_refused(self):
        self.skipTest("pending — TDD")

    def test_reorder_recomputes(self):
        self.skipTest("pending — TDD")

    def test_move_between_days_tracked_in_chatter(self):
        self.skipTest("pending — TDD")

    def test_day_totals(self):
        self.skipTest("pending — TDD")

    def test_views_load(self):
        self.skipTest("pending — TDD")
