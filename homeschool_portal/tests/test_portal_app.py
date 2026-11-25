# -*- coding: utf-8 -*-
"""UC-P6 — The portal as an app on the Bemade portal kit (19.0.3.0.0).

Acceptance criteria
-------------------
1. With the kit's switch on, a learner (a student's own login) lands on « Today »
   (``/my/home``, the kit's dashboard) with the homeschool widgets for HIS student:
   today's list, today's blocks, today's reading entry. Ticking a line on the card
   ticks it (same record effect as the day page) and comes back to « Today » with
   the line shown done.
2. The learner's nav: Today · Week · Traces · Reading (Practice comes with
   ``homeschool_practice``); a nav entry opens the section of his student.
3. Week, Traces (list, page with its comments, hand-in form with files) and Reading
   (books, book page with the entry form) render inside the shell for the learner and
   the tutor, with the same data and permissions as before (another family's student
   is still a 404).
4. A tutor (resource user) gets the same nav, a learner switcher when he follows two
   learners (the URLs keep naming the student), « Today » for the learner he picks,
   and cannot tick (no tick-box, the route refuses).
5. A login that is both a learner and a tutor gets both roles and the app without
   errors.
6. Internal users (the parents, homeschool managers) never get the shell: they read
   the pages on the stock portal.
7. The installed app: the homeschool app's manifest (``/my/app/homeschool.webmanifest``;
   ``/my/app.webmanifest`` where it is the database's default app) starts on « Today »
   (``/my/home``, also its id) and offers « Today » as a shortcut.
8. The brand name is the company's, never a hard-coded name.
9. Switch off: every route answers the stock portal pages, without error.
10. French for a fr_CA user: « Today » (its widgets), the nav and the role in the user
    menu. With ``website`` installed (the shared addons CI) the test also activates
    fr_CA on every website and sets the ``frontend_lang`` cookie (no-op otherwise).
"""
import json

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from .common import HomeschoolPortalCase

SHELL = 'data-pk-app-shell="1"'
SWITCH = "bemade_portal_kit.enabled"
DEFAULT_APP = "bemade_portal_kit.default_app"


@tagged("post_install", "-at_install")
class TestPortalApp(HomeschoolPortalCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env["ir.config_parameter"].sudo().set_param(SWITCH, "1")
        cls.today = fields.Date.context_today(cls.student_user)
        Day, Block, Deliverable = env["homeschool.day"], env["homeschool.block"], env["homeschool.deliverable"]
        cls.day_today = Day.create({"student_id": cls.student.id, "date": cls.today})
        cls.b_today = Block.create({
            "day_id": cls.day_today.id, "name": "Fractions workshop", "kind": "bloc", "subject_id": cls.math.id,
            "duration_planned": 30, "sequence": 1,
        })
        cls.d_today = Deliverable.create({"day_id": cls.day_today.id, "name": "Glue the fraction strip", "sequence": 1})
        cls.d_today_bonus = Deliverable.create({
            "day_id": cls.day_today.id, "name": "Draw a pizza in eighths", "bonus": True, "sequence": 2,
        })
        # family B's day today (the tutor's second learner)
        cls.day_b_today = Day.with_company(cls.company_b).create({"student_id": cls.student_b.id, "date": cls.today})
        cls.d_b_today = Deliverable.create({"day_id": cls.day_b_today.id, "name": "Wire the robot arm"})

    def follow_both(self):
        """The teacher follows the two learners (two families)."""
        self.student_b.resource_user_ids = [Command.link(self.teacher.id)]

    # 1 -------------------------------------------------------------------
    def test_learner_lands_on_today(self):
        self.login(self.student_user)
        res = self.get("/my")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn(SHELL, body)
        for widget in ("hs_list", "hs_blocks", "hs_reading"):
            self.assertIn('data-pk-dash-widget="%s"' % widget, body)
        self.assertIn("Today's list", body)
        self.assertIn("Glue the fraction strip", body)
        self.assertIn("Fractions workshop", body)
        self.assertIn("The Lighthouse Cat", body)   # the book in progress
        self.assertIn('data-hs-reading="todo"', body)
        self.assertNotIn("Wire the robot arm", body)  # never another family's list
        self.assertIn('%s/deliverable/%d/tick' % (self.base(), self.d_today.id), body)

    def test_learner_cannot_configure_today(self):
        # Today is set up for the learner: no « Configure » link, and the page sends him back
        self.login(self.student_user)
        self.assertNotIn("o_pk_dash_configure", self.text(self.get("/my/home")))
        res = self.get("/my/app/dashboard/configure", allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertTrue(res.headers["Location"].endswith("/my/home"))

    def test_tick_from_the_card(self):
        self.login(self.student_user)
        body = self.text(self.get("/my/home"))
        self.assertIn('name="return_url" value="/my/home?student_id=%d"' % self.student.id, body)
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d_today.id),
                        {"done": "1", "return_url": "/my/home?student_id=%d" % self.student.id},
                        allow_redirects=False)
        self.assertIn(res.status_code, (302, 303))
        self.assertTrue(res.headers["Location"].endswith("/my/home?student_id=%d" % self.student.id))
        self.refresh()
        self.assertTrue(self.d_today.done)
        self.assertEqual(self.d_today.done_by, self.student_user)
        body = self.text(self.get("/my/home"))
        self.assertRegex(body, r'o_hs_dash_line o_hs_done"\s+data-hs-line="%d"' % self.d_today.id)
        self.assertIn("Ticked off.", body)  # the toast
        # untick, back again
        self.post("%s/deliverable/%d/tick" % (self.base(), self.d_today.id), {"done": "0", "return_url": "/my/home"})
        self.refresh()
        self.assertFalse(self.d_today.done)

    def test_tick_return_url_is_same_site_only(self):
        self.login(self.student_user)
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d_today.id),
                        {"done": "1", "return_url": "https://evil.example/"}, allow_redirects=False)
        self.assertIn("/day/%s" % self.today, res.headers["Location"])

    # 2 -------------------------------------------------------------------
    def test_learner_nav(self):
        self.login(self.student_user)
        body = self.text(self.get("/my/home"))
        for key in ("hs_today", "hs_week", "hs_traces", "hs_reading"):
            self.assertIn('data-pk-nav-key="%s"' % key, body)
        self.assertRegex(body, r'data-pk-nav-key="hs_today"\s+aria-current="page"')
        for section in ("week", "traces", "reading", "day"):
            res = self.get("/my/homeschool/%s" % section, allow_redirects=False)
            self.assertIn(res.status_code, (302, 303), section)
            self.assertTrue(res.headers["Location"].endswith("%s/%s" % (self.base(), section)), section)

    # 3 -------------------------------------------------------------------
    def _pages(self):
        base = self.base()
        return {
            "week": base + "/week/2026-W10",
            "day": base + "/day/2026-03-02",
            "traces": base + "/traces",
            "trace": "%s/traces/%d" % (base, self.trace_inst.id),
            "submit": base + "/traces/submit",
            "reading": base + "/reading",
            "book": "%s/reading/%d" % (base, self.book.id),
            "home": "/my/homeschool",
        }

    def test_pages_in_the_shell(self):
        for user in (self.student_user, self.teacher):
            self.login(user)
            pages = self._pages()
            for name, url in pages.items():
                res = self.get(url)
                self.assertEqual(res.status_code, 200, (user.login, name))
                self.assertIn(SHELL, res.text, (user.login, name))
            body = self.text(self.get(pages["week"]))
            self.assertIn("Segment 1 - sentences", body)
            self.assertRegex(body, r'data-pk-nav-key="hs_week"\s+aria-current="page"')
            body = self.text(self.get(pages["trace"]))
            self.assertIn("Kingston poster", body)
            self.assertIn("I drew the fort.", body)
            self.assertIn("o_portal_chatter", body)  # the comments
            self.assertNotIn("Private note", self.text(self.get(pages["traces"])))
            self.assertIn('type="file"', self.text(self.get(pages["submit"])))
            body = self.text(self.get(pages["book"]))
            self.assertIn("harbour", body)
            if user == self.student_user:
                self.assertIn('name="word1"', body)
            else:
                self.assertNotIn('name="word1"', body)
        # the stock pills are the shell's nav now
        self.assertNotIn("nav-pills", self.text(self.get(self.base() + "/week")))

    @mute_logger("odoo.http")
    def test_permissions_unchanged(self):
        self.login(self.student_user)
        other = self.base(self.student_b)
        for url in (other + "/week", other + "/traces", "%s/traces/%d" % (self.base(), self.trace_b.id),
                    "%s/reading/%d" % (self.base(), self.book_b.id)):
            self.assertEqual(self.get(url).status_code, 404, url)

    def test_hand_in_with_files_in_the_shell(self):
        self.login(self.student_user)
        res = self.post(self.base() + "/traces/submit",
                        {"name": "Fraction strip photo", "date": str(self.today), "student_comment": "Eighths!"},
                        files=[("files", ("strip.jpg", b"\xff\xd8\xff fake", "image/jpeg"))])
        self.assertEqual(res.status_code, 200)
        trace = self.env["homeschool.trace"].search([("name", "=", "Fraction strip photo")])
        self.assertEqual(len(trace), 1)
        self.assertFalse(trace.validated)
        self.assertEqual(trace.attachment_ids.mapped("name"), ["strip.jpg"])
        self.assertIn(SHELL, res.text)

    def test_entry_form_in_the_shell(self):
        self.login(self.student_user)
        self.post("%s/reading/%d/entry" % (self.base(), self.book.id),
                  {"date": str(self.today), "word1": "tide", "word2": "gull"})
        entry = self.env["homeschool.reading.entry"].search([("book_id", "=", self.book.id), ("date", "=", self.today)])
        self.assertEqual(entry.word1, "tide")
        body = self.text(self.get("/my/home"))
        self.assertIn('data-hs-reading="done"', body)

    # 4 -------------------------------------------------------------------
    def test_tutor_with_two_learners(self):
        self.follow_both()
        self.login(self.teacher)
        self.assertEqual(self.teacher._pk_roles() & {"learner", "tutor"}, {"tutor"})
        body = self.text(self.get("/my/home?student_id=%d" % self.student.id))
        self.assertIn(SHELL, body)
        for key in ("hs_today", "hs_week", "hs_traces", "hs_reading"):
            self.assertIn('data-pk-nav-key="%s"' % key, body)
        self.assertIn('data-hs-switcher="1"', body)
        self.assertIn('data-hs-learner="%d"' % self.student.id, body)
        self.assertIn('data-hs-learner="%d"' % self.student_b.id, body)
        self.assertIn("Glue the fraction strip", body)
        self.assertNotIn("Wire the robot arm", body)
        self.assertNotIn("/deliverable/%d/tick" % self.d_today.id, body)  # read-only list
        # the other learner: from the switcher, then remembered for the nav entries
        body = self.text(self.get("/my/home?student_id=%d" % self.student_b.id))
        self.assertIn("Wire the robot arm", body)
        self.assertNotIn("Glue the fraction strip", body)
        res = self.get("/my/homeschool/week", allow_redirects=False)
        self.assertTrue(res.headers["Location"].endswith(self.base(self.student_b) + "/week"))
        # on a student page, the switcher keeps the section, not the record
        body = self.text(self.get("%s/traces/%d" % (self.base(), self.trace_inst.id)))
        self.assertIn('href="%s/traces"' % self.base(self.student_b), body)

    def test_tutor_alone_has_no_switcher(self):
        self.login(self.teacher)
        body = self.text(self.get("/my/home"))
        self.assertIn(SHELL, body)
        self.assertNotIn('data-hs-switcher="1"', body)
        self.assertIn("Glue the fraction strip", body)

    @mute_logger("odoo.http")
    def test_tutor_cannot_tick(self):
        self.login(self.teacher)
        res = self.post("%s/deliverable/%d/tick" % (self.base(), self.d_today.id),
                        {"done": "1", "return_url": "/my/home"})
        self.assertEqual(res.status_code, 403)
        self.refresh()
        self.assertFalse(self.d_today.done)

    # 5 -------------------------------------------------------------------
    def test_learner_and_tutor(self):
        self.student_b.resource_user_ids = [Command.link(self.student_user.id)]
        self.assertEqual(self.student_user._pk_roles() & {"learner", "tutor"}, {"learner", "tutor"})
        self.login(self.student_user)
        res = self.get("/my/home")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn(SHELL, body)
        self.assertIn('data-hs-switcher="1"', body)
        self.assertIn("Glue the fraction strip", body)  # his own day first
        body = self.text(self.get("/my/home?student_id=%d" % self.student_b.id))
        self.assertIn("Wire the robot arm", body)
        self.assertNotIn("/deliverable/%d/tick" % self.d_b_today.id, body)  # a learner he only follows
        for url in (self.base(self.student_b) + "/week", self.base() + "/week"):
            self.assertEqual(self.get(url).status_code, 200, url)

    # 6 -------------------------------------------------------------------
    def test_internal_users_never_get_the_shell(self):
        env = self.env
        parent = env["res.users"].create({
            "name": "Parent Example", "login": "hsp_parent", "password": "hsp_parent",
            "group_ids": [Command.set([
                env.ref("base.group_user").id, env.ref("homeschool.group_homeschool_manager").id,
            ])],
        })
        # (a resource user must be a portal user: the core refuses an internal one)
        self.assertFalse(parent._pk_roles() & {"learner", "tutor"})
        self.assertFalse(env["portal.kit"].with_user(parent)._pk_shell_active())
        self.login(parent)
        for url in ("/my/home", "/my/homeschool", "/my/app/more"):
            res = self.get(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertNotIn(SHELL, res.text, url)

    # 7 -------------------------------------------------------------------
    def test_installable_app(self):
        # The homeschool app's own manifest, whatever the database's default app.
        manifest = json.loads(self.get("/my/app/homeschool.webmanifest").text)
        self.assertEqual((manifest["start_url"], manifest["id"]), ("/my/home", "/my/home"))
        self.assertIn({"name": "Today", "url": "/my/home"}, manifest.get("shortcuts", []))
        # The homeschool instance: the only (default) app answers /my/app.webmanifest,
        # the URL an installed app keeps.
        self.env["ir.config_parameter"].sudo().set_param(DEFAULT_APP, "homeschool")
        res = self.get("/my/app.webmanifest")
        self.assertEqual(res.status_code, 200)
        manifest = json.loads(res.text)
        self.assertEqual(manifest["start_url"], "/my/home")
        self.assertEqual(manifest["id"], "/my/home")
        self.assertIn({"name": "Today", "url": "/my/home"}, manifest.get("shortcuts", []))
        self.login(self.student_user)
        self.assertIn("/my/app.webmanifest", self.get("/my/home").text)

    # 8 -------------------------------------------------------------------
    def test_brand_is_the_company(self):
        self.env.company.name = "Maple Grove School"
        self.login(self.student_user)
        body = self.text(self.get("/my/home"))
        self.assertIn('o_pk_rail_brand_name">Maple Grove School<', body)

    # 9 -------------------------------------------------------------------
    def test_switch_off_falls_back(self):
        self.env["ir.config_parameter"].sudo().set_param(SWITCH, "0")
        for user in (self.student_user, self.teacher):
            self.login(user)
            urls = dict(self._pages(), today="/my/home")
            for name, url in urls.items():
                res = self.get(url)
                self.assertEqual(res.status_code, 200, (user.login, name))
                self.assertNotIn(SHELL, res.text, (user.login, name))
        self.login(self.student_user)
        self.assertIn("nav-pills", self.text(self.get(self.base() + "/week")))

    # 10 ------------------------------------------------------------------
    def test_french(self):
        env = self.env
        env["res.lang"]._activate_lang("fr_CA")
        env["ir.module.module"]._load_module_terms(
            ["homeschool", "homeschool_portal", "bemade_portal_kit", "bemade_portal_kit_dashboard"], ["fr_CA"])
        self.student_user.lang = "fr_CA"
        self.login(self.student_user)
        if env["ir.module.module"]._get("website").state == "installed":
            lang = env["res.lang"]._lang_get("fr_CA")
            for website in env["website"].sudo().search([]):
                if lang not in website.language_ids:
                    website.language_ids = [Command.link(lang.id)]
            self.opener.cookies.set("frontend_lang", "fr_CA")
        body = self.text(self.get("/my/home"))
        for text in ("Liste du jour", "Blocs du jour", "Lecture du jour", "Aujourd'hui", "Semaine", "Lecture", "Élève",
                     "Entrée à écrire"):
            self.assertIn(text, body)
        self.assertNotIn("Today's list", body)
        body = self.text(self.get(self.base() + "/week/2026-W10"))
        self.assertIn("Semaine 2026-W10", body)
        # A tutor's « Configure »: the homeschool app's page, under « Aujourd'hui »
        self.teacher.lang = "fr_CA"
        self.login(self.teacher)
        if env["ir.module.module"]._get("website").state == "installed":
            self.opener.cookies.set("frontend_lang", "fr_CA")
        res = self.get("/my/app/dashboard/configure")
        self.assertEqual(res.status_code, 200)
        body = self.text(res)
        self.assertIn("Configurer le tableau de bord", body)
        self.assertIn("Aujourd'hui", body)
        self.assertNotIn("Tableau de bord<", body)  # never the kit's own home as the parent
