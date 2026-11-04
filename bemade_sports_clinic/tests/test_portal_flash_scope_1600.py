"""Task 1600 — the portal « flash » (error + posted form, kept in the session
for the Post/Redirect/Get round-trip) is SCOPED to the form it belongs to and
EXPIRES. Synthetic fixtures only (public repository).

Root cause being closed: a flash stashed by player A's failed save stayed in
the session until ANY form popped it; the player edit form then filled player
B's fields from A's posted data and unticked B's teams, and saving B wrote A's
identity onto B.

Acceptance criteria covered:

* AC-a1 A flash stranded by player A's failed save neither pre-fills nor
  unticks anything on player B's edit form, and is discarded by that visit.
* AC-a2 The flash still works for its own form: A's edit form shows the error
  and A's posted values.
* AC-a3 An expired flash (more than 10 minutes) is ignored.
* AC-a4 Each flash route is scoped: player create, team add-player, contact
  add, contact edit, event create — the flash shows on its own form only.
* AC-h  The #1600 replay: A's failed save strands a flash; B's form is opened
  and saved exactly as the browser posts it — B's identity and teams are
  untouched.
"""
import time
from unittest.mock import patch

from lxml import html as lxml_html

from odoo import Command
from odoo.tests import tagged

from .portal_cov_common import PortalCovCommon

MIXIN = 'odoo.addons.bemade_sports_clinic.controllers.access_control_mixin.systime.time'


def form_payload(page, form_id):
    """What a browser posts for ``form_id`` on ``page`` (no JS)."""
    tree = lxml_html.fromstring(page)
    form = tree.get_element_by_id(form_id)
    data = []
    for node in form.iter('input', 'textarea', 'select'):
        name = node.get('name')
        if not name or node.get('disabled') is not None:
            continue
        if node.tag == 'input':
            kind = (node.get('type') or 'text').lower()
            if kind in ('checkbox', 'radio'):
                if node.get('checked') is not None:
                    data.append((name, node.get('value') or 'on'))
                continue
            if kind in ('submit', 'button'):
                continue
            data.append((name, node.get('value') or ''))
        elif node.tag == 'textarea':
            data.append((name, node.text or ''))
        else:
            selected = [opt for opt in node.iter('option') if opt.get('selected') is not None]
            options = selected or list(node.iter('option'))[:1]
            data.append((name, options[0].get('value') if options else ''))
    return data


@tagged('-at_install', 'post_install')
class TestPortalFlashScope1600(PortalCovCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.team_c = env['sports.team'].create({'name': 'PC Team C 1600', 'parent_id': cls.org.id})
        env['sports.team.staff'].create({
            'team_id': cls.team_c.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })
        # Player A (whose save fails) and player B (opened next), both on the
        # therapist's teams, with a full identity.
        cls.player.write({'date_of_birth': '2008-03-04', 'position': 'Goalie'})
        cls.player_b2 = env['sports.patient'].create({
            'first_name': 'Bea', 'last_name': 'Synthetic', 'date_of_birth': '2009-05-06',
            'team_ids': [Command.set([cls.team_a.id, cls.team_c.id])],
            'position': 'Winger',
        })

    def _strand_flash_on_a(self, **extra):
        """A's save refused (invalid DOB): a flash for A is left behind."""
        data = {
            'csrf_token': self._csrf(),
            'patient_id': self.player.id,
            'first_name': 'Strandedfirst', 'last_name': 'Strandedlast',
            'date_of_birth': 'not-a-date',
            'position': 'Strandedposition',
            # A's form posted without B's teams.
            'team_ids': str(self.team_a.id),
        }
        data.update(extra)
        resp = self.url_open('/my/player/save', data=data, allow_redirects=False)
        self.assertEqual(resp.status_code, 303)
        self.assertIn('/my/player/edit?patient_id=%s' % self.player.id, resp.headers['Location'])

    def _edit_page(self, patient):
        resp = self.url_open('/my/player/edit?patient_id=%s' % patient.id)
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        return resp.text

    def _assert_b_form_is_b(self, page):
        fields = dict(form_payload(page, 'edit-player-form'))
        self.assertEqual(fields['first_name'], 'Bea')
        self.assertEqual(fields['last_name'], 'Synthetic')
        self.assertEqual(fields['date_of_birth'], '2009-05-06')
        self.assertEqual(fields['position'], 'Winger')
        teams = {value for name, value in form_payload(page, 'edit-player-form') if name == 'team_ids'}
        self.assertEqual(teams, {str(self.team_a.id), str(self.team_c.id)},
                         "B's teams must stay ticked")
        self.assertNotIn('Strandedfirst', page)
        self.assertNotIn('Please enter a valid Date of Birth', page)

    # ----- AC-a1 -----
    def test_stranded_flash_does_not_fill_another_player(self):
        self._login_tp()
        self._strand_flash_on_a()
        self._assert_b_form_is_b(self._edit_page(self.player_b2))
        # Discarded by that visit: A's own form no longer shows it either.
        page_a = self._edit_page(self.player)
        self.assertNotIn('Strandedfirst', page_a)

    # ----- AC-a2 -----
    def test_flash_shows_on_its_own_form(self):
        self._login_tp()
        self._strand_flash_on_a()
        page_a = self._edit_page(self.player)
        self.assertIn('Please enter a valid Date of Birth', page_a)
        self.assertEqual(dict(form_payload(page_a, 'edit-player-form'))['first_name'], 'Strandedfirst')
        # Popped: a second visit is clean.
        self.assertNotIn('Strandedfirst', self._edit_page(self.player))

    # ----- AC-a3 -----
    def test_expired_flash_is_ignored(self):
        self._login_tp()
        self._strand_flash_on_a()
        later = time.time() + 601
        with patch(MIXIN, return_value=later):
            page_a = self._edit_page(self.player)
        self.assertNotIn('Strandedfirst', page_a)
        self.assertNotIn('Please enter a valid Date of Birth', page_a)

    # ----- AC-h -----
    def test_replay_1600(self):
        self._login_tp()
        self._strand_flash_on_a()
        page_b = self._edit_page(self.player_b2)
        data = form_payload(page_b, 'edit-player-form')
        resp = self.url_open('/my/player/save', data=data, allow_redirects=False)
        self.assertEqual(resp.status_code, 303, resp.text[:300])
        self.assertNotIn('/my/player/edit', resp.headers['Location'])
        self.player_b2.invalidate_recordset()
        self.assertEqual(
            (self.player_b2.first_name, self.player_b2.last_name,
             str(self.player_b2.date_of_birth), self.player_b2.position),
            ('Bea', 'Synthetic', '2009-05-06', 'Winger'))
        self.assertEqual(self.player_b2.team_ids, self.team_a | self.team_c)
        self.player.invalidate_recordset()
        self.assertEqual((self.player.first_name, self.player.last_name), ('Pat', 'One'))

    # ----- AC-a4: every flash route is scoped -----
    def _assert_flash_only_on(self, own_url, other_url, marker):
        other = self.url_open(other_url)
        self.assertNotIn(marker, other.text, "the flash leaked onto %s" % other_url)

    def test_player_create_flash_scoped(self):
        self._login_tp()
        self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Createfirst', 'last_name': '',
        }, allow_redirects=False)
        own = self.url_open('/my/player/create')
        self.assertIn('First name and last name are required', own.text)
        self.url_open('/my/player/create/save', data={
            'csrf_token': self._csrf(), 'first_name': 'Createfirst', 'last_name': '',
        }, allow_redirects=False)
        self._assert_flash_only_on(None, '/my/player/edit?patient_id=%s' % self.player.id,
                                   'Createfirst')

    def test_team_add_flash_scoped(self):
        self._login_tp()
        url = '/my/team/%s/add_player' % self.team_a.id
        post = {'csrf_token': self._csrf(), 'first_name': 'Teamfirst', 'last_name': 'Teamlast',
                'date_of_birth': 'garbage'}
        self.url_open(url + '/submit', data=post, allow_redirects=False)
        self.assertIn('Teamfirst', self.url_open(url).text)
        self.url_open(url + '/submit', data=post, allow_redirects=False)
        self.assertNotIn('Teamfirst', self.url_open('/my/team/%s/add_player' % self.team_c.id).text)
        self.url_open(url + '/submit', data=post, allow_redirects=False)
        self._assert_flash_only_on(None, '/my/player/create', 'Teamfirst')

    def test_contact_flash_scoped(self):
        self._login_tp()
        required = 'Name and contact type are required fields'

        def add_on_a():
            self.url_open('/my/player/contact/save', data={
                'csrf_token': self._csrf(), 'patient_id': self.player.id,
                'name': '', 'contact_type': 'mother', 'email': 'flash1600@example.com',
            }, allow_redirects=False)

        def edit_contact():
            self.url_open('/my/player/contact/update', data={
                'csrf_token': self._csrf(), 'contact_id': self.contact.id,
                'name': '', 'contact_type': 'mother',
            }, allow_redirects=False)

        # A's add form: not on B's add form, shown on A's.
        add_on_a()
        self.assertNotIn('flash1600@example.com', self.url_open(
            '/my/player/contact/add?patient_id=%s' % self.player_b2.id).text)
        add_on_a()
        page = self.url_open('/my/player/contact/add?patient_id=%s' % self.player.id).text
        self.assertIn('flash1600@example.com', page)
        self.assertIn(required, page)
        # The contact's edit form: never shown on an add form.
        edit_contact()
        self.assertNotIn(required, self.url_open(
            '/my/player/contact/add?patient_id=%s' % self.player.id).text)
        edit_contact()
        self.assertIn(required, self.url_open(
            '/my/player/contact/edit?contact_id=%s' % self.contact.id).text)

    def test_event_create_flash_scoped(self):
        self._login_tp()
        post = {'csrf_token': self._csrf(), 'name': 'Eventflash 1600',
                'team_ids': str(self.team_a.id), 'event_type': 'game'}
        self.url_open('/my/event/create/submit', data=post, allow_redirects=False)
        self.assertIn('Eventflash 1600', self.url_open('/my/event/create').text)
        self.url_open('/my/event/create/submit', data=post, allow_redirects=False)
        self._assert_flash_only_on(None, '/my/player/create', 'Eventflash 1600')
        self.assertNotIn('Eventflash 1600', self.url_open('/my/event/create').text,
                         "a foreign visit discards the flash")
