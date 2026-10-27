"""Task 1723 — « adding an event doesn't work » (MC, internal user, en_CA).
Synthetic fixtures only. Reproduction notes: see the dev-review artifact.

Acceptance criteria:

* AC-1 (silent failure) A server-side refusal rendered as
  ``[data-sc-field-error]`` (event / therapist times) is read by the form
  guard: the message shows under its field and nothing typed is lost (was:
  the form reloaded empty with no message).
* AC-2 (forgiving team picker) A team name typed exactly (accents, case,
  spaces ignored) and never picked is picked when leaving the box; typed
  text matching nothing shows an inline error and the submit is refused
  with it (never a silent drop).
* AC-3 Changing the organisation drops the other organisation's teams and
  says so (« The teams of another organization were removed. »).
* AC-4 Typed-then-picked keeps working.
* AC-5 Both an internal user in en_CA (MC's shape: internal administrator,
  no team staff) and a portal therapist, phone and laptop.
* AC-6 French: the new messages.
"""
from odoo import Command
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_event_org_team_filter_1597 import Org1597Common


class Create1723Common(Org1597Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('en_CA')
        cls.mc = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'Synthetic Internal Admin 1723', 'login': 'sc1723.internal@example.com',
            'password': 'sc1723-internal-pw', 'lang': 'en_CA',
            # MC's groups on staging: internal, Settings admin and the
            # sports clinic « Administrator » (no team staff row).
            'group_ids': [Command.set([env.ref('base.group_user').id, env.ref('base.group_system').id,
                                       env.ref('bemade_sports_clinic.group_sports_clinic_admin').id])],
        })

    def _run(self, tour, login):
        self._switch(True)
        self.start_tour('/my/event/create', tour, login=login)

    def _event(self, name):
        return self.env['sports.event'].search([('name', '=', name)])


class _Tours1723:

    def test_internal_typed_then_picked(self):
        self._run('sc_1723_typed_then_picked', 'sc1723.internal@example.com')
        self.assertEqual(self._event('SC 1723 Picked').team_ids, self.team_a)

    def test_internal_typed_exact(self):
        self._run('sc_1723_typed_exact', 'sc1723.internal@example.com')
        self.assertEqual(self._event('SC 1723 Exact').team_ids, self.team_a)

    def test_portal_typed_exact(self):
        self._run('sc_1723_typed_exact', 'pc.tp@example.com')
        self.assertEqual(self._event('SC 1723 Exact').team_ids, self.team_a)

    def test_internal_typed_nothing(self):
        self._run('sc_1723_typed_nothing', 'sc1723.internal@example.com')
        self.assertFalse(self._event('SC 1723 Nothing'))

    def test_portal_server_refusal_kept(self):
        self._run('sc_1723_server_refusal_kept', 'pc.tp@example.com')
        self.assertFalse(self._event('SC 1723 Refused'))

    def test_internal_server_refusal_kept(self):
        self._run('sc_1723_server_refusal_kept', 'sc1723.internal@example.com')
        self.assertFalse(self._event('SC 1723 Refused'))

    def test_org_drop_notice(self):
        self._run('sc_1723_org_drop_notice', 'p77.cadmin@example.com')


@tagged('post_install', '-at_install')
class TestEventCreatePhone1723(_Tours1723, Create1723Common):
    allow_inherited_tests_method = True
    browser_size = '390x844'


@tagged('post_install', '-at_install')
class TestEventCreateLaptop1723(_Tours1723, Create1723Common):
    allow_inherited_tests_method = True
    browser_size = '1366x768'
