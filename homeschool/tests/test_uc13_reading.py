# -*- coding: utf-8 -*-
"""UC-13 — Reading log (carnet de lecture): a book per student, one entry per day.

Acceptance criteria
-------------------
1. ``homeschool.reading.book``: ``student_id`` (required), ``company_id`` (the student's
   family), ``title`` (required), ``author``, ``started``, ``finished``, ``entry_ids``.
2. ``homeschool.reading.entry``: ``book_id`` (required, cascade), ``student_id`` /
   ``company_id`` from the book, ``date`` (default today), ``word1``, ``word2``,
   ``question``, ``answer``, ``weekly_page`` (the Friday page), ``written_by``.
   **One entry per book per day** (SQL constraint).
3. The **portal student** reads his own books and creates / writes his own entries
   (``written_by`` is always himself); another student's book → AccessError; he cannot
   move an entry to another student's book; no unlink.
4. A **resource user** reads the books and entries of the students he is attached to
   and cannot write.
5. Managers see the books of their companies only.
"""
from datetime import date

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tools.misc import mute_logger

from .common import HomeschoolCase


class TestReading(HomeschoolCase):
    def setUp(self):
        super().setUp()
        self.book = self.Book.create({"student_id": self.student.id, "title": "The Lighthouse Keeper's Cat", "author": "A. Invented", "started": date(2026, 3, 2)})
        self.book_b = self.Book.create({"student_id": self.student_b.id, "title": "Robots on Mars", "started": date(2026, 3, 2)})

    # ------------------------------------------------------------------
    # 1 + 2. fields, company, one entry per day
    # ------------------------------------------------------------------
    def test_book_company_follows_student(self):
        self.assertEqual(self.book.company_id, self.company)
        self.assertEqual(self.book_b.company_id, self.company_b)
        self.assertEqual(self.book.display_name, "The Lighthouse Keeper's Cat")
        self.assertFalse(self.book.finished)
        self.assertEqual(self.book.entry_count, 0)

    def test_entry_fields_and_unique_per_day(self):
        e1 = self.Entry.create({"book_id": self.book.id, "date": date(2026, 3, 2), "word1": "harbour", "word2": "lantern",
                                "question": "Why does the cat climb the tower?", "answer": "To see the boats."})
        self.assertEqual((e1.student_id, e1.company_id), (self.student, self.company))
        self.assertEqual(e1.written_by, self.env.user)
        self.assertEqual(self.book.entry_ids, e1)
        self.assertEqual(self.book.entry_count, 1)
        # same book, same day: refused
        with mute_logger("odoo.sql_db"), self.assertRaises(Exception):
            self.Entry.create({"book_id": self.book.id, "date": date(2026, 3, 2), "word1": "again"})
        # same day, other book: fine; other day, same book: fine
        self.Entry.create({"book_id": self.book_b.id, "date": date(2026, 3, 2), "word1": "rover"})
        friday = self.Entry.create({"book_id": self.book.id, "date": date(2026, 3, 6), "weekly_page": "This week the cat learned to swim."})
        self.assertEqual(friday.date.weekday(), 4)
        self.assertEqual(self.book.entry_count, 2)
        # default date is today
        today = self.Entry.create({"book_id": self.book.id})
        self.assertEqual(today.date, fields.Date.context_today(self.Entry))
        # cascade
        self.book.unlink()
        self.assertFalse(self.Entry.search([("id", "in", (e1 | friday | today).ids)]))

    # ------------------------------------------------------------------
    # 3. portal student: own entries only
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_student_writes_own_entries(self):
        portal = self.portal_user()
        self.student.user_id = portal
        Book = self.Book.with_user(portal)
        Entry = self.Entry.with_user(portal)
        self.assertTrue(Book.has_access("read"))
        self.assertFalse(Book.has_access("write") or Book.has_access("create"))
        self.assertTrue(Entry.has_access("read") and Entry.has_access("write") and Entry.has_access("create"))
        self.assertFalse(Entry.has_access("unlink"))
        # sees his own book, not the other family's
        self.assertEqual(Book.search([]), self.book.with_user(portal))
        with self.assertRaises(AccessError):
            self.book_b.with_user(portal).read(["title"])
        # writes an entry; written_by is himself even if he says otherwise
        e = Entry.create({"book_id": self.book.id, "date": date(2026, 3, 3), "word1": "gull", "written_by": self.env.user.id})
        self.assertEqual(e.written_by, portal)
        self.assertEqual((e.student_id, e.company_id), (self.student, self.company))
        e.write({"answer": "Because it is hungry.", "word2": "fog"})
        self.assertEqual(self.book.entry_ids, e)
        # not on the other student's book, not moved there either
        with self.assertRaises(AccessError):
            Entry.create({"book_id": self.book_b.id, "date": date(2026, 3, 3), "word1": "no"})
        with self.assertRaises(AccessError):
            e.write({"book_id": self.book_b.id})
        self.assertEqual(e.book_id, self.book)
        # the other student's entries are invisible
        other = self.Entry.create({"book_id": self.book_b.id, "date": date(2026, 3, 3), "word1": "crater"})
        self.assertEqual(Entry.search([]), e)
        with self.assertRaises(AccessError):
            other.with_user(portal).read(["word1"])
        with self.assertRaises(AccessError):
            other.with_user(portal).write({"word1": "x"})
        # no unlink, no book edits
        with self.assertRaises(AccessError):
            e.unlink()
        with self.assertRaises(AccessError):
            self.book.with_user(portal).write({"finished": date(2026, 3, 20)})

    # ------------------------------------------------------------------
    # 4. resource user: read only
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_model", "odoo.addons.base.models.ir_rule")
    def test_resource_reads_only(self):
        e = self.Entry.create({"book_id": self.book.id, "date": date(2026, 3, 2), "word1": "harbour"})
        e_b = self.Entry.create({"book_id": self.book_b.id, "date": date(2026, 3, 2), "word1": "rover"})
        teacher = self.resource_user(self.student)
        self.assertEqual(self.Book.with_user(teacher).search([]), self.book.with_user(teacher))
        self.assertEqual(self.Entry.with_user(teacher).search([]), e.with_user(teacher))
        e.with_user(teacher).read(["word1", "answer", "weekly_page"])
        with self.assertRaises(AccessError):
            e.with_user(teacher).write({"answer": "no"})
        with self.assertRaises(AccessError):
            self.Entry.with_user(teacher).create({"book_id": self.book.id, "date": date(2026, 3, 9)})
        with self.assertRaises(AccessError):
            e_b.with_user(teacher).read(["word1"])
        # attached to both: both families' books
        self.student_b.resource_user_ids = [fields.Command.link(teacher.id)]
        self.assertEqual(self.Book.with_user(teacher).search([]), (self.book | self.book_b).with_user(teacher))

    # ------------------------------------------------------------------
    # 5. managers by company
    # ------------------------------------------------------------------
    @mute_logger("odoo.addons.base.models.ir_rule")
    def test_manager_scoped_by_company(self):
        e_b = self.Entry.create({"book_id": self.book_b.id, "date": date(2026, 3, 2), "word1": "rover"})
        manager_b = self.manager_user(self.company_b, login="hs_manager_b")
        self.assertEqual(self.Book.with_user(manager_b).search([]), self.book_b.with_user(manager_b))
        self.assertEqual(self.Entry.with_user(manager_b).search([]), e_b.with_user(manager_b))
        with self.assertRaises(AccessError):
            self.book.with_user(manager_b).read(["title"])
        manager_b_env = self.Book.with_user(manager_b).with_company(self.company_b)
        book = manager_b_env.create({"student_id": self.student_b.id, "title": "A second book"})
        self.assertEqual(book.company_id, self.company_b)
