# -*- coding: utf-8 -*-
"""UC-P2 — The day page, the day's list and the week grid.

Acceptance criteria
-------------------
1. ``/my/homeschool/<student>/day/<date>`` shows the blocks in sequence with kind,
   times, intention / steps / success / fallback rendered from Markdown (sanitized
   HTML), the institutional material of the day with a file link (never the internal
   material), the day's list, previous / next school day. Without a date: today. A
   date without a school day says so; an invalid date is a 404.
2. The student ticks a line of his list (``done``, ``done_at``, ``done_by`` stamped) and
   unticks it (cleared). A resource user sees the list read-only and cannot tick (403).
3. Cross-student URLs are 404: another family's day, another family's deliverable.
4. ``/my/homeschool/<student>/week/<iso-week>`` shows the five-day grid with the blocks
   (name, kind, duration), the days off, links to the days and to the adjacent weeks.
"""
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import HomeschoolPortalCase


@tagged("post_install", "-at_install")
class TestPortalDayWeek(HomeschoolPortalCase):

    def test_student_day_page(self):
        self.login(self.student_user)
        res = self.get(self.base() + "/day/2026-03-02")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        # blocks, in sequence, with kind and times
        for name in ("Opening circle", "Segment 1 - sentences", "Pause", "Reading alone"):
            self.assertIn(name, body)
        self.assertLess(body.index("Opening circle"), body.index("Segment 1 - sentences"))
        self.assertLess(body.index("Segment 1 - sentences"), body.index("Reading alone"))
        self.assertIn("09:00", body)
        self.assertIn("14:00", body)  # anchored block
        self.assertIn("Opening", body)
        # markdown rendered, not escaped
        self.assertIn("<strong>three</strong>", body)
        self.assertIn("<li>Underline the verb</li>", body)
        self.assertIn("Three sentences, each with a verb.", body)
        self.assertIn("One sentence, then a break.", body)
        self.assertIn("<strong>sentences</strong>", body)  # the day's opening
        # the day's list
        self.assertIn("Liste du jour", body)
        self.assertIn("Copy the sentence", body)
        self.assertIn("Extra reading", body)
        self.assertIn("/deliverable/%d/tick" % self.d1.id, body)
        # material: institutional with its PDF, never the internal one
        self.assertIn("Test fiche", body)
        self.assertIn("%s/file/%d" % (self.base(), self.pdf_att.id), body)
        self.assertNotIn("Secret worksheet", body)
        # navigation
        self.assertIn("/day/2026-03-03", body)
        self.assertNotIn("/day/2026-03-01", body)
        # the PDF downloads
        res = self.get("%s/file/%d" % (self.base(), self.pdf_att.id))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, b"%PDF-1.4 fiche\n")
        self.assertIn("attachment", res.headers.get("Content-Disposition", ""))

    def test_day_off_and_empty_days(self):
        self.login(self.student_user)
        body = self.text(self.get(self.base() + "/day/2026-03-04"))
        self.assertIn("Day off", body)
        self.assertIn("Field trip", body)
        res = self.get(self.base() + "/day/2026-03-09")
        self.assertEqual(res.status_code, 200)
        self.assertIn("No school day is planned on this date.", self.text(res))
        self.assertIn("/day/2026-03-04", self.text(res))  # previous school day
        # default: today
        self.assertEqual(self.get(self.base() + "/day").status_code, 200)
        self.assertEqual(self.get(self.base()).status_code, 200)

    @mute_logger("odoo.http")
    def test_invalid_date_is_404(self):
        self.login(self.student_user)
        self.assertEqual(self.get(self.base() + "/day/not-a-date").status_code, 404)
        self.assertEqual(self.get(self.base() + "/day/2026-13-45").status_code, 404)

    def test_student_ticks_and_unticks(self):
        self.login(self.student_user)
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d1.id), {"done": "1"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("ticked=%d" % self.d1.id, res.url)
        self.refresh()
        self.assertTrue(self.d1.done)
        self.assertTrue(self.d1.done_at)
        self.assertEqual(self.d1.done_by, self.student_user)
        self.assertIn("fa-check-square-o", self.text(res))
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d1.id), {"done": "0"})
        self.assertEqual(res.status_code, 200)
        self.refresh()
        self.assertFalse(self.d1.done or self.d1.done_at or self.d1.done_by)

    @mute_logger("odoo.http")
    def test_teacher_reads_the_list_but_cannot_tick(self):
        self.login(self.teacher)
        body = self.text(self.get(self.base() + "/day/2026-03-02"))
        self.assertIn("Copy the sentence", body)
        self.assertNotIn("/deliverable/%d/tick" % self.d1.id, body)  # no form
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d1.id), {"done": "1"})
        self.assertEqual(res.status_code, 403)
        self.refresh()
        self.assertFalse(self.d1.done)

    @mute_logger("odoo.http")
    def test_cross_student_urls_are_404(self):
        self.login(self.student_user)
        self.assertEqual(self.get(self.base(self.student_b) + "/day/2026-03-02").status_code, 404)
        self.assertEqual(self.get(self.base(self.student_b) + "/week/2026-W10").status_code, 404)
        # another family's deliverable, through his own student's URL or the other's
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d_b.id), {"done": "1"})
        self.assertEqual(res.status_code, 404)
        res = self.post("%s/deliverable/%d/tick" % (self.base(self.student_b), self.d_b.id), {"done": "1"})
        self.assertEqual(res.status_code, 404)
        self.refresh()
        self.assertFalse(self.d_b.done)
        # the other family's student never sees family A
        self.login(self.student_b_user)
        self.assertEqual(self.get(self.base() + "/day/2026-03-02").status_code, 404)
        body = self.text(self.get(self.base(self.student_b) + "/day/2026-03-02"))
        self.assertIn("Robots segment", body)
        self.assertNotIn("Segment 1", body)

    @mute_logger("odoo.http")
    def test_week_grid(self):
        self.login(self.student_user)
        res = self.get(self.base() + "/week/2026-W10")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("Week 2026-W10", body)
        self.assertIn("Segment 1 - sentences", body)
        self.assertIn("Segment 2 - time", body)
        self.assertIn("Day off", body)
        self.assertIn("45 min", body)
        self.assertIn("/day/2026-03-02", body)
        self.assertIn("/day/2026-03-03", body)
        self.assertIn("/week/2026-W09", body)
        self.assertIn("/week/2026-W11", body)
        self.assertNotIn("Robots segment", body)
        self.assertEqual(self.get(self.base() + "/week").status_code, 200)
        self.assertEqual(self.get(self.base() + "/week/2026-W99").status_code, 404)
        self.assertEqual(self.get(self.base() + "/week/garbage").status_code, 404)
        # the teacher sees the same grid
        self.login(self.teacher)
        self.assertIn("Segment 2 - time", self.text(self.get(self.base() + "/week/2026-W10")))
