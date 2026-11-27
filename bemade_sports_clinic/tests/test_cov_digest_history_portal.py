"""Task 1389 — portal digest snapshot-history route coverage.

Acceptance criteria exercised here (controller-level; the modal JS click-through
is verified separately at /dev-review):

- A member (coach AND TP) gets their team's snapshots on both the full page and
  the ?preview=1 modal fragment.
- The modal fragment is limited to the last DIGEST_HISTORY_MODAL_DAYS days.
- The full page paginates (standard portal pager, 20/page).
- Coach and TP see the SAME date list (dates carry no content — no leak).
- A non-member gets 403 on both modes.
- A crafted off-site `back` param is rejected (falls back to the team dashboard).
"""
import re
from datetime import date, datetime, timedelta

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('post_install', '-at_install')
class TestDigestHistoryPortal(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Digest = cls.env['sports.team.digest']
        cls.today = date.today()
        # 25 consecutive daily snapshots on team_a (newest = today) so the full
        # page needs a second pager page (20/page).
        cls.snapshots = Digest
        for i in range(25):
            d = cls.today - timedelta(days=i)
            cls.snapshots |= Digest.create({
                'team_id': cls.team_a.id,
                'snapshot_date': d,
                'captured_at': datetime.combine(d, datetime.min.time()),
                'item_data': {},
            })
        # A snapshot on the OTHER team, to prove scoping.
        cls.other_snap = Digest.create({
            'team_id': cls.team_b.id,
            'snapshot_date': cls.today,
            'captured_at': datetime.combine(cls.today, datetime.min.time()),
            'item_data': {},
        })

    def _page_url(self, **kw):
        url = '/my/team/%d/digest-history' % self.team_a.id
        if kw:
            url += '?' + '&'.join('%s=%s' % (k, v) for k, v in kw.items())
        return url

    def _preview_url(self):
        return '/my/team/%d/digest-history/recent' % self.team_a.id

    def _digest_ids(self, text):
        """Task 1541: the team_a snapshots a rendered app page links to (its
        rows carry the page link and the lazy ``/body`` link)."""
        return set(re.findall(r'/my/team/%d/digest/(\d+)' % self.team_a.id, text))

    def _dates_in(self, text):
        """Snapshot ISO dates present in a rendered response."""
        return set(re.findall(r'\d{4}-\d{2}-\d{2}', text))

    def test_page_member_lists_snapshots(self):
        """A coach member gets a 200 page listing team_a snapshots."""
        self._login_coach()
        resp = self.url_open(self._page_url())
        self.assertEqual(resp.status_code, 200)
        # Task 1541: the app's page lists each date as a row (its digest link).
        self.assertTrue(self._digest_ids(resp.text))
        # team_b's snapshot must NOT appear (scoping); its date equals today so we
        # instead assert the link to team_b's digest is absent.
        self.assertNotIn('/my/team/%d/digest/%d' % (self.team_b.id, self.other_snap.id),
                         resp.text)

    def test_page_pagination(self):
        """25 snapshots -> 20 on page 1, 5 on page 2, pager rendered."""
        self._login_tp()
        p1 = self.url_open(self._page_url())
        self.assertEqual(p1.status_code, 200)
        links1 = self._digest_ids(p1.text)
        self.assertEqual(len(links1), 20)
        # Pager present -> the standard portal /page/2 link is rendered.
        self.assertIn('/digest-history/page/2', p1.text)
        p2 = self.url_open('/my/team/%d/digest-history/page/2' % self.team_a.id)
        self.assertEqual(p2.status_code, 200)
        links2 = self._digest_ids(p2.text)
        self.assertEqual(len(links2), 5)
        self.assertFalse(links1 & links2)


    def test_coach_and_tp_same_date_list(self):
        """Dates carry no content: coach and TP see an identical date set."""
        self._login_coach()
        coach_dates = self._digest_ids(self.url_open(self._page_url()).text)
        self._login_tp()
        tp_dates = self._digest_ids(self.url_open(self._page_url()).text)
        self.assertTrue(coach_dates)
        self.assertEqual(coach_dates, tp_dates)

    def test_non_member_403(self):
        """A plain portal user (no team) is forbidden on both modes."""
        self._login_plain()
        self.assertEqual(self.url_open(self._page_url()).status_code, 403)
        # Task 1541: the modal fragment is gone for everyone.
        self.assertEqual(self.url_open(self._preview_url()).status_code, 404)

    def test_back_param_offsite_rejected(self):
        """A crafted off-site back falls back to the team dashboard link."""
        self._login_coach()
        resp = self.url_open(self._page_url(back='https://evil.example.com/x'))
        self.assertEqual(resp.status_code, 200)
        # Task 1541: the app page's navigation is the parent registry's; the
        # crafted back is never a link (it may ride, URL-encoded, in the
        # pager / app-bar query strings, sanitized again on use).
        from lxml import html as lxml_html
        hrefs = lxml_html.fromstring(resp.text).xpath('//a/@href | //form/@action')
        self.assertFalse([h for h in hrefs if 'evil.example.com' in h.split('?')[0]
                          or h.startswith(('http://evil', 'https://evil', '//evil'))])

    def test_back_param_local_preserved(self):
        """A valid local /my/... back is honoured on the backlink."""
        self._login_coach()
        local = '/my/team?team_id=%d' % self.team_a.id
        resp = self.url_open(self._page_url(back=local.replace('?', '%3F').replace('=', '%3D')))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/my/team?team_id=%d' % self.team_a.id, resp.text)
