# -*- coding: utf-8 -*-
"""Shared fixtures for the portal tests.

Everything is invented: two families (companies), a student with his own portal login,
an outside teacher attached to him, an unrelated portal user, a second family's student.
Names, titles and dates are synthetic and tied to no real household.
"""
import html
from datetime import date

from odoo import Command, http
from odoo.tests import HttpCase

MONDAY = date(2026, 3, 2)
TUESDAY = date(2026, 3, 3)
WEDNESDAY = date(2026, 3, 4)


class HomeschoolPortalCase(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True, mail_create_nolog=True, mail_notrack=True))
        env = cls.env
        portal_group = env.ref("base.group_portal")
        cls.company = env.company
        cls.company_b = env["res.company"].create({"name": "Second Family"})

        def portal_user(name, login, partner=None):
            vals = {"name": name, "login": login, "password": login, "group_ids": [Command.set([portal_group.id])]}
            if partner:
                vals["partner_id"] = partner.id
            return env["res.users"].create(vals)

        # family A: the student and his login, the outside teacher
        cls.partner = env["res.partner"].create({"name": "Sam Example", "email": "sam@example.test"})
        cls.student_user = portal_user("Sam Example", "hsp_student", cls.partner)
        cls.student = env["homeschool.student"].create({
            "partner_id": cls.partner.id, "birthdate": "2015-03-01", "user_id": cls.student_user.id,
        })
        cls.teacher = portal_user("Outside Teacher", "hsp_teacher")
        cls.student.resource_user_ids = [Command.link(cls.teacher.id)]
        cls.stranger = portal_user("Unrelated Person", "hsp_stranger")

        # family B: its own student and login (never any data of family A)
        cls.partner_b = env["res.partner"].create({"name": "Other Student", "company_id": cls.company_b.id})
        cls.student_b_user = portal_user("Other Student", "hsp_student_b", cls.partner_b)
        cls.student_b = env["homeschool.student"].with_company(cls.company_b).create({
            "partner_id": cls.partner_b.id, "birthdate": "2016-07-15", "user_id": cls.student_b_user.id,
        })

        cls.fle = env.ref("homeschool.subject_fle")
        cls.math = env.ref("homeschool.subject_math")
        Day, Block = env["homeschool.day"], env["homeschool.block"]
        Deliverable, Material = env["homeschool.deliverable"], env["homeschool.material"]
        Trace, Attachment = env["homeschool.trace"], env["ir.attachment"]
        Book, Entry = env["homeschool.reading.book"], env["homeschool.reading.entry"]

        # the days of family A
        cls.day = Day.create({"student_id": cls.student.id, "date": MONDAY, "opening": "Today: **sentences** and time."})
        cls.b_open = Block.create({
            "day_id": cls.day.id, "name": "Opening circle", "kind": "opening", "duration_planned": 10, "sequence": 1,
        })
        cls.b_fle = Block.create({
            "day_id": cls.day.id, "name": "Segment 1 - sentences", "kind": "bloc", "subject_id": cls.fle.id,
            "duration_planned": 45, "sequence": 2,
            "intention": "Write **three** sentences.",
            "steps": "- Read the model\n- Copy it\n- Underline the verb",
            "success": "Three sentences, each with a verb.",
            "fallback": "One sentence, then a break.",
        })
        cls.b_pause = Block.create({"day_id": cls.day.id, "name": "Pause", "kind": "pause", "duration_planned": 15, "sequence": 3})
        cls.b_read = Block.create({
            "day_id": cls.day.id, "name": "Reading alone", "kind": "reading", "duration_planned": 20, "sequence": 4,
            "anchored": True, "start_fixed": 14.0,
        })
        cls.day_tue = Day.create({"student_id": cls.student.id, "date": TUESDAY})
        cls.b_math = Block.create({
            "day_id": cls.day_tue.id, "name": "Segment 2 - time", "kind": "bloc", "subject_id": cls.math.id,
            "duration_planned": 45, "sequence": 1,
        })
        cls.day_wed = Day.create({"student_id": cls.student.id, "date": WEDNESDAY, "is_off": True, "off_reason": "Field trip"})

        # material: one institutional (with its PDF), one internal (never on the portal)
        cls.material = Material.create({
            "name": "Test fiche", "kind": "fiche", "diffusion": "institutional", "block_ids": [Command.link(cls.b_fle.id)],
        })
        cls.pdf_att = Attachment.create({
            "name": "test-fiche.pdf", "raw": b"%PDF-1.4 fiche\n", "res_model": "homeschool.material", "res_id": cls.material.id,
        })
        cls.material.pdf_attachment_id = cls.pdf_att
        cls.material_internal = Material.create({
            "name": "Secret worksheet", "kind": "worksheet", "diffusion": "internal", "block_ids": [Command.link(cls.b_fle.id)],
        })

        # the day's list
        cls.d1 = Deliverable.create({"day_id": cls.day.id, "name": "Copy the sentence", "when": "9 h", "sequence": 1})
        cls.d2 = Deliverable.create({"day_id": cls.day.id, "name": "Extra reading", "when": "bonus", "bonus": True, "sequence": 2})

        # traces: institutional (with a linked file and a file uploaded before the record
        # existed), internal, pending by the student, pending by the teacher
        cls.trace_inst = Trace.create({
            "name": "Kingston poster", "student_id": cls.student.id, "date": date(2026, 2, 20),
            "diffusion": "institutional", "student_comment": "I drew the fort.",
            "subject_ids": [Command.set([cls.fle.id, cls.math.id])],
        })
        cls.att_linked = Attachment.create({
            "name": "poster.pdf", "raw": b"%PDF-1.4 poster\n", "res_model": "homeschool.trace", "res_id": cls.trace_inst.id,
        })
        cls.att_orphan = Attachment.create({
            "name": "photo.jpg", "raw": b"\xff\xd8\xff fake jpeg", "res_model": "homeschool.trace", "res_id": 0,
        })
        cls.trace_inst.attachment_ids = [Command.set([cls.att_linked.id, cls.att_orphan.id])]
        cls.trace_internal = Trace.create({"name": "Private note", "student_id": cls.student.id, "date": date(2026, 2, 21)})
        cls.att_internal = Attachment.create({
            "name": "private.pdf", "raw": b"%PDF-1.4 private\n", "res_model": "homeschool.trace", "res_id": cls.trace_internal.id,
        })
        cls.trace_internal.attachment_ids = [Command.link(cls.att_internal.id)]
        cls.trace_pending_student = Trace.with_user(cls.student_user).create({
            "name": "My drawing", "student_id": cls.student.id, "date": date(2026, 2, 25), "student_comment": "I liked it.",
        })
        cls.trace_pending_teacher = Trace.with_user(cls.teacher).create({
            "name": "Teacher observation", "student_id": cls.student.id, "date": date(2026, 2, 26),
        })

        # the reading log
        cls.book = Book.create({"student_id": cls.student.id, "title": "The Lighthouse Cat", "author": "A. Invented", "started": MONDAY})
        cls.entry = Entry.create({
            "book_id": cls.book.id, "date": MONDAY, "word1": "harbour", "word2": "lantern",
            "question": "Why does the cat climb the tower?", "answer": "To see the boats.",
        })

        # family B
        cls.day_b = Day.with_company(cls.company_b).create({"student_id": cls.student_b.id, "date": MONDAY})
        cls.b_b = Block.create({"day_id": cls.day_b.id, "name": "Robots segment", "kind": "bloc", "duration_planned": 30, "sequence": 1})
        cls.d_b = Deliverable.create({"day_id": cls.day_b.id, "name": "Other family task"})
        cls.trace_b = Trace.with_company(cls.company_b).create({
            "name": "Other family trace", "student_id": cls.student_b.id, "diffusion": "institutional",
        })
        cls.book_b = Book.with_company(cls.company_b).create({"student_id": cls.student_b.id, "title": "Robots on Mars", "started": MONDAY})

    # helpers -----------------------------------------------------------
    def base(self, student=None):
        return "/my/homeschool/%d" % (student or self.student).id

    def login(self, user):
        self.authenticate(user.login, user.login)

    def get(self, url, **kw):
        return self.url_open(url, **kw)

    def post(self, url, data=None, files=None, **kw):
        data = dict(data or {}, csrf_token=http.Request.csrf_token(self))
        return self.url_open(url, data=data, files=files, **kw)

    def rpc(self, url, **params):
        res = self.url_open(url, json={"jsonrpc": "2.0", "method": "call", "id": 1, "params": params})
        return res.json()

    @staticmethod
    def text(res):
        return html.unescape(res.text)

    def refresh(self):
        self.env.invalidate_all()
