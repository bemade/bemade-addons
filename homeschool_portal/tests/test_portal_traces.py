# -*- coding: utf-8 -*-
"""UC-P3 — Traces: the list, the trace page with its files and chatter, the submission.

Acceptance criteria
-------------------
1. ``/my/homeschool/<student>/traces`` lists the institutional traces of the student and
   the user's own pending traces; never an internal trace, never another user's pending
   trace. A pending trace is flagged.
2. The trace page shows the student's own words and the files; every file downloads
   through the portal — including one uploaded before the record was saved (``res_id``
   0). An internal trace's page and files are 404, as are another family's.
3. The submission form creates a trace **as the user**: ``internal``, not validated,
   ``submitted_by`` student or resource, with the files attached and the student's own
   words; then shows it as pending. Validation errors are reported, nothing is created.
4. The resource user comments on a trace through the standard portal chatter route.
5. An unrelated portal user reaches nothing (404).
6. The subjects of a trace are shown, on the list and on the trace page, read as the
   user (core 19.0.5.0.0: subjects are readable by portal users).
7. A resource's submission with a file is readable back through ``/file/<id>`` as the
   resource, and — once the parent validated it institutional — as the student, all of
   it as the user: ``controllers/portal.py`` holds no ``sudo()`` at all.
"""
import os

from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import HomeschoolPortalCase


@tagged("post_install", "-at_install")
class TestPortalTraces(HomeschoolPortalCase):

    def test_student_list(self):
        self.login(self.student_user)
        res = self.get(self.base() + "/traces")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("Kingston poster", body)
        self.assertIn("My drawing", body)
        self.assertIn("Pending validation", body)
        self.assertNotIn("Private note", body)
        self.assertNotIn("Teacher observation", body)
        self.assertNotIn("Other family trace", body)
        self.assertIn("/traces/submit", body)

    def test_teacher_list(self):
        self.login(self.teacher)
        body = self.text(self.get(self.base() + "/traces"))
        self.assertIn("Kingston poster", body)
        self.assertIn("Teacher observation", body)
        self.assertNotIn("My drawing", body)
        self.assertNotIn("Private note", body)

    @mute_logger("odoo.http")
    def test_trace_page_and_files(self):
        self.login(self.student_user)
        res = self.get("%s/traces/%d" % (self.base(), self.trace_inst.id))
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("Kingston poster", body)
        self.assertIn("I drew the fort.", body)
        self.assertIn("Institutional", body)
        self.assertIn("poster.pdf", body)
        self.assertIn("photo.jpg", body)
        # the chatter is mounted on the trace
        self.assertIn('data-res_model="homeschool.trace"', body)
        self.assertIn('data-res_id="%d"' % self.trace_inst.id, body)
        # both files download: the linked one and the one with res_id 0
        res = self.get("%s/file/%d" % (self.base(), self.att_linked.id))
        self.assertEqual((res.status_code, res.content), (200, b"%PDF-1.4 poster\n"))
        res = self.get("%s/file/%d" % (self.base(), self.att_orphan.id))
        self.assertEqual((res.status_code, res.content), (200, b"\xff\xd8\xff fake jpeg"))
        self.assertIn("attachment", res.headers.get("Content-Disposition", ""))
        # internal trace: neither the page nor its file
        self.assertEqual(self.get("%s/traces/%d" % (self.base(), self.trace_internal.id)).status_code, 404)
        self.assertEqual(self.get("%s/file/%d" % (self.base(), self.att_internal.id)).status_code, 404)
        # the teacher's pending trace: not the student's business
        self.assertEqual(self.get("%s/traces/%d" % (self.base(), self.trace_pending_teacher.id)).status_code, 404)
        # another family's trace, through either URL
        self.assertEqual(self.get("%s/traces/%d" % (self.base(), self.trace_b.id)).status_code, 404)
        self.assertEqual(self.get("%s/traces/%d" % (self.base(self.student_b), self.trace_b.id)).status_code, 404)
        # his own pending trace
        body = self.text(self.get("%s/traces/%d" % (self.base(), self.trace_pending_student.id)))
        self.assertIn("My drawing", body)
        self.assertIn("Pending validation", body)

    def test_student_submits_with_files(self):
        self.login(self.student_user)
        self.assertEqual(self.get(self.base() + "/traces/submit").status_code, 200)
        res = self.post(
            self.base() + "/traces/submit",
            {"name": "My volcano model", "date": "2026-03-02", "student_comment": "It erupted twice.",
             "diffusion": "institutional", "validated": "1", "submitted_by": "parent"},
            files=[("files", ("volcano.jpg", b"\xff\xd8\xff volcano", "image/jpeg")),
                   ("files", ("notes.txt", b"lava, ash, crater", "text/plain"))],
        )
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("Thank you! The trace was handed in.", body)
        self.assertIn("Pending validation", body)
        self.refresh()
        trace = self.env["homeschool.trace"].search([("name", "=", "My volcano model")])
        self.assertEqual(len(trace), 1)
        self.assertEqual((trace.submitted_by, trace.diffusion, trace.validated), ("student", "internal", False))
        self.assertEqual((trace.student_id, trace.company_id, trace.create_uid), (self.student, self.company, self.student_user))
        self.assertEqual(trace.student_comment, "It erupted twice.")
        self.assertEqual(str(trace.date), "2026-03-02")
        self.assertEqual(sorted(trace.attachment_ids.mapped("name")), ["notes.txt", "volcano.jpg"])
        for att in trace.attachment_ids:
            self.assertEqual((att.res_model, att.res_id), ("homeschool.trace", trace.id))
        self.assertEqual(trace.attachment_ids.filtered(lambda a: a.name == "notes.txt").raw, b"lava, ash, crater")
        self.assertIn("/traces/%d" % trace.id, res.url)
        # the files download for the submitter
        att = trace.attachment_ids.filtered(lambda a: a.name == "volcano.jpg")
        res = self.get("%s/file/%d" % (self.base(), att.id))
        self.assertEqual((res.status_code, res.content), (200, b"\xff\xd8\xff volcano"))
        # listed as pending for the submitter, invisible to the teacher
        self.assertIn("My volcano model", self.text(self.get(self.base() + "/traces")))
        self.login(self.teacher)
        self.assertNotIn("My volcano model", self.text(self.get(self.base() + "/traces")))

    def test_teacher_submits(self):
        self.login(self.teacher)
        res = self.post(self.base() + "/traces/submit", {"name": "Reading assessment", "date": "2026-03-03"})
        self.assertEqual(res.status_code, 200)
        self.refresh()
        trace = self.env["homeschool.trace"].search([("name", "=", "Reading assessment")])
        self.assertEqual((trace.submitted_by, trace.diffusion, trace.validated), ("resource", "internal", False))
        self.assertEqual((trace.student_id, trace.create_uid), (self.student, self.teacher))
        self.assertFalse(trace.attachment_ids)
        self.assertIn("Reading assessment", self.text(self.get(self.base() + "/traces")))
        self.login(self.student_user)
        self.assertNotIn("Reading assessment", self.text(self.get(self.base() + "/traces")))

    def test_submission_errors(self):
        self.login(self.student_user)
        before = self.env["homeschool.trace"].search_count([])
        res = self.post(self.base() + "/traces/submit", {"name": "   ", "date": "2026-03-02"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("Give your trace a title.", self.text(res))
        res = self.post(self.base() + "/traces/submit", {"name": "Late", "date": "yesterday"})
        self.assertIn("The date is not valid.", self.text(res))
        self.refresh()
        self.assertEqual(self.env["homeschool.trace"].search_count([]), before)

    @mute_logger("odoo.http")
    def test_stranger_cannot_submit(self):
        self.login(self.stranger)
        self.assertEqual(self.get(self.base() + "/traces").status_code, 404)
        self.assertEqual(self.get(self.base() + "/traces/submit").status_code, 404)
        res = self.post(self.base() + "/traces/submit", {"name": "Intruder", "date": "2026-03-02"})
        self.assertEqual(res.status_code, 404)
        self.refresh()
        self.assertFalse(self.env["homeschool.trace"].search([("name", "=", "Intruder")]))
        self.assertEqual(self.get("%s/file/%d" % (self.base(), self.att_linked.id)).status_code, 404)

    @mute_logger("odoo.http", "odoo.addons.base.models.ir_rule", "odoo.addons.base.models.ir_model")
    def test_teacher_comments_through_the_chatter(self):
        self.login(self.teacher)
        result = self.rpc(
            "/mail/message/post",
            thread_model="homeschool.trace", thread_id=self.trace_inst.id,
            post_data={"body": "Well done on the poster!"},
        )
        self.assertNotIn("error", result, result)
        message = self.env["mail.message"].browse(result["result"]["message_id"])
        self.assertEqual((message.model, message.res_id), ("homeschool.trace", self.trace_inst.id))
        self.assertEqual(message.author_id, self.teacher.partner_id)
        self.assertEqual(message.message_type, "comment")
        self.assertEqual(message.subtype_id, self.env.ref("mail.mt_comment"))
        self.assertIn("Well done on the poster!", message.body)
        # the student reads it back through the portal fetch route
        self.login(self.student_user)
        fetched = self.rpc("/mail/chatter_fetch", thread_model="homeschool.trace", thread_id=self.trace_inst.id)
        self.assertIn(message.id, fetched["result"]["messages"])
        # nobody posts on a trace he cannot read
        self.login(self.stranger)
        result = self.rpc(
            "/mail/message/post",
            thread_model="homeschool.trace", thread_id=self.trace_inst.id, post_data={"body": "Hello?"},
        )
        self.assertIn("error", result)
        self.login(self.student_user)
        result = self.rpc(
            "/mail/message/post",
            thread_model="homeschool.trace", thread_id=self.trace_internal.id, post_data={"body": "Hello?"},
        )
        self.assertIn("error", result)

    def test_trace_subjects_listed(self):
        self.login(self.student_user)
        body = self.text(self.get(self.base() + "/traces"))
        self.assertIn("French", body)
        self.assertIn("Mathematics", body)
        body = self.text(self.get("%s/traces/%d" % (self.base(), self.trace_inst.id)))
        self.assertIn("Subjects:", body)
        self.assertLess(body.index("French"), body.index("Mathematics"))
        # the teacher too
        self.login(self.teacher)
        self.assertIn("Mathematics", self.text(self.get("%s/traces/%d" % (self.base(), self.trace_inst.id))))

    @mute_logger("odoo.http", "odoo.addons.base.models.ir_rule", "odoo.addons.base.models.ir_model")
    def test_teacher_file_readable_by_teacher_then_student(self):
        self.login(self.teacher)
        res = self.post(
            self.base() + "/traces/submit",
            {"name": "Reading assessment with file", "date": "2026-03-03"},
            files=[("files", ("assessment.pdf", b"%PDF-1.4 assessment\n", "application/pdf"))],
        )
        self.assertEqual(res.status_code, 200)
        self.refresh()
        trace = self.env["homeschool.trace"].search([("name", "=", "Reading assessment with file")])
        att = trace.attachment_ids
        self.assertEqual(len(att), 1)
        self.assertEqual((att.res_model, att.res_id, att.create_uid), ("homeschool.trace", trace.id, self.teacher))
        # the resource reads his file back; the student cannot see the pending trace nor its file
        res = self.get("%s/file/%d" % (self.base(), att.id))
        self.assertEqual((res.status_code, res.content), (200, b"%PDF-1.4 assessment\n"))
        self.assertIn("assessment.pdf", self.text(self.get("%s/traces/%d" % (self.base(), trace.id))))
        self.login(self.student_user)
        self.assertEqual(self.get("%s/traces/%d" % (self.base(), trace.id)).status_code, 404)
        self.assertEqual(self.get("%s/file/%d" % (self.base(), att.id)).status_code, 404)
        # the parent validates it institutional: the student reads the trace and its file
        trace.action_validate(diffusion="institutional")
        body = self.text(self.get("%s/traces/%d" % (self.base(), trace.id)))
        self.assertIn("assessment.pdf", body)
        res = self.get("%s/file/%d" % (self.base(), att.id))
        self.assertEqual((res.status_code, res.content), (200, b"%PDF-1.4 assessment\n"))
        # and the teacher still does
        self.login(self.teacher)
        self.assertEqual(self.get("%s/file/%d" % (self.base(), att.id)).status_code, 200)

    def test_no_sudo_in_controller(self):
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "controllers", "portal.py")
        with open(path, encoding="utf-8") as fh:
            self.assertNotIn("sudo(", fh.read(), "the portal runs nothing as superuser")
