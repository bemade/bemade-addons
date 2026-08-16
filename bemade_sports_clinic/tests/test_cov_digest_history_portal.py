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

    def _dates_in(self, text):
        """Snapshot ISO dates present in a rendered response."""
        return set(re.findall(r'\d{4}-\d{2}-\d{2}', text))

    def test_page_member_lists_snapshots(self):
        """A coach member gets a 200 page listing team_a snapshots."""
        self._login_coach()
        resp = self.url_open(self._page_url())
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.today.isoformat(), resp.text)
        # team_b's snapshot must NOT appear (scoping); its date equals today so we
        # instead assert the link to team_b's digest is absent.
        self.assertNotIn('/my/team/%d/digest/%d' % (self.team_b.id, self.other_snap.id),
                         resp.text)

    def test_page_pagination(self):
        """25 snapshots -> 20 on page 1, 5 on page 2, pager rendered."""
        self._login_tp()
        p1 = self.url_open(self._page_url())
        self.assertEqual(p1.status_code, 200)
        links1 = re.findall(r'/my/team/%d/digest/\d+' % self.team_a.id, p1.text)
        self.assertEqual(len(links1), 20)
        # Pager present -> the standard portal /page/2 link is rendered.
        self.assertIn('/digest-history/page/2', p1.text)
        p2 = self.url_open('/my/team/%d/digest-history/page/2' % self.team_a.id)
        self.assertEqual(p2.status_code, 200)
        links2 = re.findall(r'/my/team/%d/digest/\d+' % self.team_a.id, p2.text)
        self.assertEqual(len(links2), 5)

    def test_preview_modal_limited_to_window(self):
        """?preview fragment shows only the last 14 days, plus the Voir tout link."""
        self._login_coach()
        resp = self.url_open(self._preview_url())
        self.assertEqual(resp.status_code, 200)
        links = re.findall(r'/my/team/%d/digest/\d+' % self.team_a.id, resp.text)
        # 14-day window inclusive of today -> at most 15 daily snapshots; here the
        # snapshots are consecutive so days 0..14 => 15 rows.
        self.assertLessEqual(len(links), 15)
        self.assertGreater(len(links), 0)
        # The oldest snapshot (24 days back) must be excluded.
        oldest = (self.today - timedelta(days=24)).isoformat()
        self.assertNotIn(oldest, resp.text)
        # "Voir tout" link to the full page is present.
        self.assertIn('/my/team/%d/digest-history' % self.team_a.id, resp.text)

    def test_coach_and_tp_same_date_list(self):
        """Dates carry no content: coach and TP see an identical date set."""
        self._login_coach()
        coach_dates = self._dates_in(self.url_open(self._page_url()).text)
        self._login_tp()
        tp_dates = self._dates_in(self.url_open(self._page_url()).text)
        self.assertTrue(coach_dates)
        self.assertEqual(coach_dates, tp_dates)

    def test_non_member_403(self):
        """A plain portal user (no team) is forbidden on both modes."""
        self._login_plain()
        self.assertEqual(self.url_open(self._page_url()).status_code, 403)
        self.assertEqual(self.url_open(self._preview_url()).status_code, 403)

    def test_back_param_offsite_rejected(self):
        """A crafted off-site back falls back to the team dashboard link."""
        self._login_coach()
        resp = self.url_open(self._page_url(back='https://evil.example.com/x'))
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('evil.example.com', resp.text)
        # Backlink defaults to the team dashboard.
        self.assertIn('href="/my/team/%d"' % self.team_a.id, resp.text)

    def test_back_param_local_preserved(self):
        """A valid local /my/... back is honoured on the backlink."""
        self._login_coach()
        local = '/my/team?team_id=%d' % self.team_a.id
        resp = self.url_open(self._page_url(back=local.replace('?', '%3F').replace('=', '%3D')))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('/my/team?team_id=%d' % self.team_a.id, resp.text)
