# -*- coding: utf-8 -*-
"""UC-P1 — The portal home and the homeschool landing page.

Acceptance criteria
-------------------
1. ``/my/homeschool`` lists the students the user may see: his own student (the
   student's login) or the students he is attached to as a resource user — and only
   those. A resource user attached to two students of two families sees both.
2. An unrelated portal user sees no student and reaches no student URL (404).
3. The portal home (``/my``) carries the card ("My school" for the student, "My
   students" for the teacher) and ``/my/counters`` reports the number of students.
4. Anonymous visitors are sent to the login page.
"""
from odoo import Command
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import HomeschoolPortalCase


@tagged("post_install", "-at_install")
class TestPortalHome(HomeschoolPortalCase):

    def test_student_sees_own_card_only(self):
        self.login(self.student_user)
        res = self.get("/my/homeschool")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("My school", body)
        self.assertIn("Sam Example", body)
        self.assertIn(self.base() + "/day", body)
        self.assertNotIn("Other Student", body)

    def test_teacher_sees_attached_students(self):
        self.login(self.teacher)
        body = self.text(self.get("/my/homeschool"))
        self.assertIn("My students", body)
        self.assertIn("Sam Example", body)
        self.assertNotIn("Other Student", body)
        # attached to the second family's student as well: both, from two companies
        self.student_b.resource_user_ids = [Command.link(self.teacher.id)]
        body = self.text(self.get("/my/homeschool"))
        self.assertIn("Sam Example", body)
        self.assertIn("Other Student", body)
        self.assertIn(self.base(self.student_b) + "/day", body)

    @mute_logger("odoo.http")
    def test_stranger_sees_nothing(self):
        self.login(self.stranger)
        res = self.get("/my/homeschool")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("No student is attached to your account yet.", body)
        self.assertNotIn("Sam Example", body)
        for url in ("/day", "/week", "/traces", "/reading"):
            self.assertEqual(self.get(self.base() + url).status_code, 404, url)

    def test_home_card_and_counter(self):
        self.login(self.student_user)
        body = self.text(self.get("/my"))
        self.assertIn('href="/my/homeschool"', body)
        self.assertIn("My school", body)
        self.assertNotIn("My students", body)
        counters = self.rpc("/my/counters", counters=["homeschool_student_count"])["result"]
        self.assertEqual(counters["homeschool_student_count"], 1)
        self.login(self.teacher)
        body = self.text(self.get("/my"))
        self.assertIn("My students", body)
        self.login(self.stranger)
        counters = self.rpc("/my/counters", counters=["homeschool_student_count"])["result"]
        self.assertEqual(counters["homeschool_student_count"], 0)

    def test_anonymous_redirected_to_login(self):
        self.authenticate(None, None)
        res = self.get("/my/homeschool", allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertIn("/web/login", res.headers.get("Location", ""))
