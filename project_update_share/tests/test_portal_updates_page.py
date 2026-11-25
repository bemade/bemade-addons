# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""Use case: the client reads a project's updates on the portal (HttpCase).

ACCEPTANCE CRITERIA
- ``/my/projects/<id>/updates``, logged in as a portal user who can open the
  project, renders the project's updates that user can read (shared with
  them, see test_portal_access) newest first, each with title, date, status
  and description, and no other update. With none, it says there are no
  updates yet.
- A portal user who cannot open the project, or an anonymous visitor, is
  sent away (redirect to ``/my`` or login) and sees no update content.
- It is NOT redirected to Project Sharing for collaborators: the link in the
  share email lands on the updates page for every recipient.
- The classic portal project page (``/my/projects/<id>``, for followers
  without Project Sharing) shows an "Updates" button at the top that leads
  to the page.
"""
from datetime import date

from odoo import Command
from odoo.tests.common import HttpCase, tagged

from .common import ProjectUpdateShareCommon


@tagged("post_install", "-at_install")
class TestPortalUpdatesPage(HttpCase, ProjectUpdateShareCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.url = "/my/projects/%s/updates" % cls.project.id
        cls._update_cls = lambda **vals: cls.Update.create({
            "status": "on_track", "project_id": cls.project.id, **vals,
        })
        cls.older = cls._update_cls(
            name="Older news", date=date(2026, 10, 1),
            description="<p>First steps.</p>",
            internal_only=False, recipient_ids=[Command.set(cls.follower.ids)],
        )
        cls.newer = cls._update_cls(
            name="Newer news", date=date(2026, 11, 1), status="at_risk",
            description="<p>Second steps.</p>",
            internal_only=False, recipient_ids=[Command.set(cls.follower.ids)],
        )
        cls._update_cls(name="Secret internal note", description="<p>Hush.</p>")

    def test_recipient_sees_shared_updates_newest_first(self):
        self.authenticate("pus-follower", "pus-follower")
        resp = self.url_open(self.url)
        self.assertEqual(resp.status_code, 200)
        page = resp.text
        for text in ("Older news", "Newer news", "First steps.", "Second steps.",
                     "At Risk", "On Track"):
            self.assertIn(text, page)
        self.assertLess(page.index("Newer news"), page.index("Older news"))
        self.assertNotIn("Secret internal note", page)
        self.assertNotIn("Hush.", page)

    def test_collaborator_lands_on_the_page_and_sees_none(self):
        # Can open the project (Project Sharing), but nothing was shared
        # with them: the page itself, not a redirect, saying so.
        self.authenticate("pus-collaborator", "pus-collaborator")
        resp = self.url_open(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.url.endswith(self.url), resp.url)
        self.assertIn("There are no updates yet.", resp.text)
        self.assertNotIn("Newer news", resp.text)

    def test_outsider_and_anonymous_are_sent_away(self):
        self.authenticate("pus-outsider", "pus-outsider")
        resp = self.url_open(self.url)
        self.assertTrue(resp.url.endswith("/my"), resp.url)
        self.assertNotIn("Newer news", resp.text)
        self.authenticate(None, None)
        resp = self.url_open(self.url)
        self.assertIn("/web/login", resp.url)
        self.assertNotIn("Newer news", resp.text)

    def test_classic_project_page_has_updates_button(self):
        self.authenticate("pus-follower", "pus-follower")
        resp = self.url_open("/my/projects/%s" % self.project.id)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('href="%s"' % self.url, resp.text)
