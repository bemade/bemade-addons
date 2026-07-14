"""Portal date/time displays must honor the user's configured language formats
(res.lang date_format / time_format) and timezone — never a hardcoded pattern
(task 1252).

Strategy: log the portal user in under fr_CA whose date_format is overridden to
the distinctive, non-ISO '%d/%m/%Y' (dd/MM/yyyy) and time_format to the 12-hour
'%I:%M:%S %p'. A hardcoded 'yyyy-MM-dd'/'HH:mm' template would still render ISO;
a lang-driven one renders the fr_CA patterns. One test per template family
(timesheets + events).

Note on assertions: the '02/02/2026' date form is locale-independent (digits +
slashes) and can never come from a hardcoded 'yyyy-MM-dd', so it is the primary
proof. The datetime-local edit inputs carry ISO values with a 'T' separator
('2026-02-02T10:00'), so a *space*-separated ISO string ('2026-02-02 10:00')
only ever came from the old hardcoded 'yyyy-MM-dd HH:mm' display — a safe
regression guard.
"""
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestCovPortalDatetimeLang(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Activate fr_CA and give it distinctive, non-ISO display formats so the
        # assertions can tell a lang-driven render from a hardcoded one. Both
        # values are members of res.lang's fixed Selection lists.
        cls.env['res.lang']._activate_lang('fr_CA')
        cls.fr = cls.env['res.lang']._lang_get('fr_CA')
        cls.fr.write({'date_format': '%d/%m/%Y', 'time_format': '%I:%M:%S %p'})
        # Pin the portal user to fr_CA + UTC (UTC avoids a tz date-shift so the
        # asserted wall-clock values are deterministic).
        cls.tp.write({'lang': 'fr_CA', 'tz': 'UTC'})

    def test_timesheet_card_datetimes_follow_lang(self):
        """The timesheet card (split date/time header + the four full-datetime
        travel/coverage cells) renders in fr_CA formats, not ISO."""
        dt = datetime(2026, 2, 2, 10, 0)
        self.timesheet.write({
            'travel_start': dt,
            'coverage_start': dt,
            'coverage_end': dt + timedelta(hours=3),
            'travel_end': dt + timedelta(hours=4),
        })

        self._login_tp()
        text = self.url_open('/my/sc/timesheets').text

        # Lang date_format (dd/MM/yyyy) — impossible under a hardcoded ISO pattern.
        self.assertIn('02/02/2026', text)
        # Full-datetime cell: lang date + lang time, seconds hidden. The '02/02/2026 10:00'
        # prefix is present whether the AM/PM marker renders as 'AM' or 'a.m.'.
        self.assertIn('02/02/2026 10:00', text)
        # Regression guard: the old hardcoded 'yyyy-MM-dd HH:mm' display is gone.
        self.assertNotIn('2026-02-02 10:00', text)

    def test_events_card_datetimes_follow_lang(self):
        """The events-list card date/time cell renders in fr_CA formats, not ISO.
        The PC Event fixture (date_start 2026-02-02 10:00) drives the date_only /
        time_only widgets."""
        self._login_tp()
        # no_default_dates disables the today-onward filter that would hide the
        # Feb-2026 fixture.
        text = self.url_open('/my/events?no_default_dates=1').text

        # Lang date_format (dd/MM/yyyy) in the date_only cell — impossible under
        # a hardcoded 'yyyy-MM-dd'.
        self.assertIn('02/02/2026', text)
