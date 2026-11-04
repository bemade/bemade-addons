# Part of Bemade Sports Clinic. See LICENSE file for full copyright and licensing details.
"""/my/counters contract (2026-08-31 prod incident).

Acceptance criteria
===================
* ``/my/counters`` must return ONLY the keys that were REQUESTED: the portal
  home JS looks up a ``[data-placeholder_count]`` element for every returned
  key and crashes on an unknown one — the spinner never clears and EVERY
  counter-revealed card stays hidden. A stray ``timesheets_count`` (orphaned
  when the placeholder was renamed to ``event_timesheets_count``) broke the
  whole portal home for every treatment professional.
* The page render path (``counters == []``) still receives no counter keys
  from this module.
"""
import json

from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon


@tagged('-at_install', 'post_install')
class TestHomeCountersContract(PortalCovCommon):

    def _counters(self, requested):
        self.authenticate('pc.tp@example.com', 'pc-tp')
        res = self.url_open(
            '/my/counters',
            data=json.dumps({'jsonrpc': '2.0', 'method': 'call',
                             'params': {'counters': requested}}),
            headers={'Content-Type': 'application/json'})
        self.assertEqual(res.status_code, 200)
        return res.json()['result']

    def test_counters_returns_only_requested_keys(self):
        for requested in (['teams_count'],
                          ['players_count', 'events_count'],
                          ['event_timesheets_count']):
            result = self._counters(requested)
            self.assertLessEqual(
                set(result), set(requested),
                "unrequested keys leaked: %s" % (set(result) - set(requested)))

    def test_counters_never_returns_orphaned_timesheets_key(self):
        result = self._counters(
            ['teams_count', 'players_count', 'activities_count',
             'events_count', 'quick_notes_count', 'clinics_count',
             'event_timesheets_count'])
        self.assertNotIn('timesheets_count', result)
