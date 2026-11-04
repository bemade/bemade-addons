"""Task 1728 — the in-app daily digest stays readable in both themes, in a
browser (phone 390 px). Synthetic fixtures only.

Acceptance criteria (static/tests/tours/sc_digest_dark_mode_1728_tours.js):

* UC-A1 Forced dark theme (the default), the day's digest page in the app
  shell: the training recommendation, the « Retour prévu » line (and its
  « · Dépassé » flag), the « Show details » link, the injury meta lines
  (location · type, « Injured since … ») and the snapshot line all read
  against their own background at ≥ 4.5:1. Before the fix the Bootstrap
  muted lines inside a card body kept the light theme's dark grey
  (rgba(33, 37, 41, .7)) on the dark card: ~1.3:1.
* UC-A2 Light theme (theme choice on, user on light): same lines, same
  ratio.
* UC-A3 The same holds in the digest history's inline body (dark).
"""
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.models.patient import PAST_RETURN_OK
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_team_changes import (
    ChangeDetailFixture,
)


class DigestDarkMode1728Common(ChangeDetailFixture, AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_change_fixture()
        today = fields.Date.today()
        cls.p.with_context(**{PAST_RETURN_OK: True}).write({
            'training_recommendation': 'Synthetic light jog only',
            'predicted_return_date': today - timedelta(days=5),
        })
        cls.knee.write({'body_location': 'Synthetic left knee'})
        cls.digest = cls.env['sports.team.digest']._capture_team(
            cls.team_a, fields.Datetime.now(), today, 'America/Toronto')
        cls.page_url = '/my/team/%s/digest/%s' % (cls.team_a.id, cls.digest.id)
        cls.history_url = '/my/team/%s/digest-history' % cls.team_a.id

    def setUp(self):
        super().setUp()
        self._switch(True)


@tagged('post_install', '-at_install')
class TestDigestDarkModeToursPhone1728(DigestDarkMode1728Common):
    browser_size = '390x844'

    def test_digest_page_dark(self):
        self._theme_choice(False)
        self.start_tour(self.page_url, 'sc_1728_digest_contrast', login='pc.tp@example.com')

    def test_digest_page_light(self):
        self._theme_choice(True)
        self.tp.sc_theme = 'light'
        self.start_tour(self.page_url, 'sc_1728_digest_contrast', login='pc.tp@example.com')

    def test_digest_history_dark(self):
        self._theme_choice(False)
        self.start_tour(self.history_url, 'sc_1728_digest_history_contrast',
                        login='pc.tp@example.com')
