# -*- coding: utf-8 -*-
"""UC-P4 — The reading log: books, entries, the student's daily form.

Acceptance criteria
-------------------
1. ``/my/homeschool/<student>/reading`` lists the student's books; the book page shows
   the entries (two words, question, answer, the Friday page).
2. The student writes today's entry (two words, question, answer, Friday page) from the
   book page; the entry is his (``written_by``); posting again for the same day completes
   the same entry (one entry per book per day).
3. The resource user reads the books and entries; he has no form and cannot post (403).
4. Another family's book is 404 through either URL.
"""
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import HomeschoolPortalCase


@tagged("post_install", "-at_install")
class TestPortalReading(HomeschoolPortalCase):

    def test_student_reading_pages(self):
        self.login(self.student_user)
        res = self.get(self.base() + "/reading")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("The Lighthouse Cat", body)
        self.assertIn("A. Invented", body)
        self.assertNotIn("Robots on Mars", body)
        res = self.get("%s/reading/%d" % (self.base(), self.book.id))
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("harbour", body)
        self.assertIn("lantern", body)
        self.assertIn("Why does the cat climb the tower?", body)
        self.assertIn("To see the boats.", body)
        self.assertIn('name="word1"', body)  # the form is his
        self.assertIn("The Friday page", body)

    def test_student_writes_and_completes_an_entry(self):
        self.login(self.student_user)
        url = "%s/reading/%d/entry" % (self.base(), self.book.id)
        res = self.post(url, {"date": "2026-03-03", "word1": "gull", "word2": "fog",
                              "question": "Where does the cat sleep?", "answer": "In the lamp room."})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Your entry is saved.", self.text(res))
        self.refresh()
        entries = self.env["homeschool.reading.entry"].search([("book_id", "=", self.book.id), ("date", "=", "2026-03-03")])
        self.assertEqual(len(entries), 1)
        self.assertEqual((entries.word1, entries.word2, entries.answer), ("gull", "fog", "In the lamp room."))
        self.assertEqual((entries.written_by, entries.student_id, entries.company_id), (self.student_user, self.student, self.company))
        # the same day again: the same entry, completed (the Friday page on a Friday)
        res = self.post(url, {"date": "2026-03-03", "word1": "gull", "word2": "fog",
                              "question": "Where does the cat sleep?", "answer": "In the lamp room, on the rug."})
        self.assertEqual(res.status_code, 200)
        self.refresh()
        entries = self.env["homeschool.reading.entry"].search([("book_id", "=", self.book.id), ("date", "=", "2026-03-03")])
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries.answer, "In the lamp room, on the rug.")
        res = self.post(url, {"date": "2026-03-06", "weekly_page": "This week the cat learned to swim."})
        self.refresh()
        friday = self.env["homeschool.reading.entry"].search([("book_id", "=", self.book.id), ("date", "=", "2026-03-06")])
        self.assertEqual(friday.weekly_page, "This week the cat learned to swim.")
        self.assertIn("This week the cat learned to swim.", self.text(res))

    @mute_logger("odoo.http")
    def test_teacher_reads_only(self):
        self.login(self.teacher)
        body = self.text(self.get(self.base() + "/reading"))
        self.assertIn("The Lighthouse Cat", body)
        res = self.get("%s/reading/%d" % (self.base(), self.book.id))
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("harbour", body)
        self.assertNotIn('name="word1"', body)
        res = self.post("%s/reading/%d/entry" % (self.base(), self.book.id), {"date": "2026-03-03", "word1": "no"})
        self.assertEqual(res.status_code, 403)
        self.refresh()
        self.assertFalse(self.env["homeschool.reading.entry"].search([("book_id", "=", self.book.id), ("date", "=", "2026-03-03")]))

    @mute_logger("odoo.http")
    def test_cross_student_books_are_404(self):
        self.login(self.student_user)
        self.assertEqual(self.get("%s/reading/%d" % (self.base(), self.book_b.id)).status_code, 404)
        self.assertEqual(self.get("%s/reading/%d" % (self.base(self.student_b), self.book_b.id)).status_code, 404)
        self.assertEqual(self.get(self.base(self.student_b) + "/reading").status_code, 404)
        res = self.post("%s/reading/%d/entry" % (self.base(), self.book_b.id), {"date": "2026-03-03", "word1": "no"})
        self.assertEqual(res.status_code, 404)
        self.refresh()
        self.assertFalse(self.env["homeschool.reading.entry"].search([("book_id", "=", self.book_b.id)]))
