"""Task 1605 — the events calendar shows each event's therapist colour.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 Colour per therapist, automatic and stable: a staff member without a
  colour gets the first palette colour nobody uses (palette order, users
  taken by id), it is stored and never changes afterwards; the palette has
  at least 24 colours and no two users share a colour while it is not
  exhausted — beyond it, further distinct hues are generated. An admin's
  colour (backend override) is kept and is never handed to someone else.
  Only ``#rrggbb`` values are accepted.
* UC-2 The feed (/my/events/calendar/data) gives every event its staff as
  ``extendedProps.staff = [{id, name, color}]`` (sudo, as the names: a coach
  sees the therapist's colour), ``[]`` for an unassigned event; the names
  list (``assigned``) is unchanged.
* UC-3 The events calendar opts in to the dots and the legend
  (``staffColors`` prop); the backend user form shows the colour to admins.
* UC-4 Tour (phone + laptop): a dot before each title — one colour, a split
  circle for two therapists, grey when unassigned; the legend under the
  calendar lists the therapists of the visible range; tapping one filters
  the calendar on that therapist (URL ``assigned_user_id``), tapping it
  again clears the filter.
* UC-5 French (fr_CA): the legend's terms are translated.
"""
import json
import re
import urllib.parse
from datetime import timedelta

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.models.res_users import SC_CALENDAR_PALETTE
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

HEX = re.compile(r'^#[0-9a-f]{6}$')


class Colours1605Common(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # Start from a blank slate: no stored colour anywhere.
        env['res.users'].with_context(active_test=False).search(
            [('sc_calendar_color', '!=', False)]).write({'sc_calendar_color': False})
        portal = env.ref('base.group_portal').id
        tp_g = env.ref('bemade_sports_clinic.group_portal_treatment_professional').id
        cls.tp2 = env['res.users'].with_context(no_reset_password=True).create({
            'name': 'ZZ Second TP 1605', 'login': 'zz.tp2.1605@example.com', 'password': 'zz-tp2-1605',
            'group_ids': [Command.set([portal, tp_g])],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team_a.id, 'partner_id': cls.tp2.partner_id.id, 'role': 'therapist'})
        start = fields.Datetime.now().replace(hour=15, minute=0, second=0, microsecond=0)
        Event = env['sports.event']

        def _event(name, staff, day=0):
            begin = start + timedelta(days=day)
            return Event.create({
                'name': name, 'event_type': 'game', 'team_ids': [Command.set([cls.team_a.id])],
                'date_start': begin, 'date_end': begin + timedelta(hours=2),
                'assigned_staff_ids': [Command.set(staff.ids)],
            })

        cls.ev_one = _event('SC 1605 Solo', cls.tp)
        cls.ev_two = _event('SC 1605 Duo', cls.tp | cls.tp2)
        cls.ev_none = _event('SC 1605 Nobody', env['res.users'])
        cls.window = 'start=%s&end=%s' % (
            urllib.parse.quote((start - timedelta(days=3)).isoformat() + 'Z'),
            urllib.parse.quote((start + timedelta(days=3)).isoformat() + 'Z'))


@tagged('post_install', '-at_install')
class TestStaffColours1605(Colours1605Common):

    _made = 0

    def _new_users(self, count):
        Users = self.env['res.users'].with_context(no_reset_password=True)
        ids = []
        for _index in range(count):
            type(self)._made += 1
            ids.append(Users.create({
                'name': 'ZZ Colour %s' % self._made, 'login': 'zz.colour.%s.1605@example.com' % self._made,
            }).id)
        return Users.browse(ids)

    # -- UC-1 ------------------------------------------------------------
    def test_palette(self):
        self.assertGreaterEqual(len(SC_CALENDAR_PALETTE), 24)
        self.assertEqual(len(set(SC_CALENDAR_PALETTE)), len(SC_CALENDAR_PALETTE))
        for colour in SC_CALENDAR_PALETTE:
            self.assertRegex(colour, HEX)

    def test_first_unused_colour_by_id_and_stable(self):
        users = self._new_users(3)
        colours = (users[2] | users[0] | users[1])._sc_calendar_colors()
        self.assertEqual([colours[user.id] for user in users], list(SC_CALENDAR_PALETTE[:3]))
        self.assertEqual(users.mapped('sc_calendar_color'), list(SC_CALENDAR_PALETTE[:3]))
        # Stable: asking again (in any order, with newcomers) changes nothing.
        newcomer = self._new_users(1)
        again = (newcomer | users)._sc_calendar_colors()
        self.assertEqual([again[user.id] for user in users], list(SC_CALENDAR_PALETTE[:3]))
        self.assertEqual(again[newcomer.id], SC_CALENDAR_PALETTE[3])

    def test_override_is_kept_and_never_reused(self):
        users = self._new_users(2)
        users[0].sc_calendar_color = SC_CALENDAR_PALETTE[0]
        colours = users._sc_calendar_colors()
        self.assertEqual(colours[users[0].id], SC_CALENDAR_PALETTE[0])
        self.assertEqual(colours[users[1].id], SC_CALENDAR_PALETTE[1])
        # An admin picks any colour (upper case is normalised).
        users[1].sc_calendar_color = '#12AB9F'
        self.assertEqual(users[1].sc_calendar_color, '#12ab9f')
        self.assertEqual(users._sc_calendar_colors()[users[1].id], '#12ab9f')

    def test_no_duplicates_even_beyond_the_palette(self):
        users = self._new_users(len(SC_CALENDAR_PALETTE) + 6)
        colours = users._sc_calendar_colors()
        values = [colours[user.id] for user in users]
        self.assertEqual(values[:len(SC_CALENDAR_PALETTE)], list(SC_CALENDAR_PALETTE))
        self.assertEqual(len(set(values)), len(values))
        for colour in values:
            self.assertRegex(colour, HEX)

    def test_only_hex_colours(self):
        user = self._new_users(1)
        for bad in ('red', '#123', '#12345g', '123456'):
            with self.assertRaises(ValidationError), mute_logger('odoo.sql_db'):
                user.sc_calendar_color = bad
        user.sc_calendar_color = False
        self.assertFalse(user.sc_calendar_color)

    # -- UC-2 ------------------------------------------------------------
    def _feed(self):
        url = '/my/events/calendar/data?%s' % self.window
        return {row['title']: row for row in self.url_open(url).json()}

    def test_feed_gives_staff_colours(self):
        self._switch(True)
        self._login_coach()  # the coach cannot read the therapists' colours
        rows = self._feed()
        tp, tp2 = self.tp.sudo(), self.tp2.sudo()
        self.assertTrue(tp.sc_calendar_color and tp2.sc_calendar_color)
        self.assertNotEqual(tp.sc_calendar_color, tp2.sc_calendar_color)
        solo = rows['SC 1605 Solo']['extendedProps']
        self.assertEqual(solo['staff'], [{'id': tp.id, 'name': 'PC TP', 'color': tp.sc_calendar_color}])
        self.assertEqual(solo['assigned'], ['PC TP'])
        duo = rows['SC 1605 Duo']['extendedProps']['staff']
        self.assertEqual({row['id']: row['color'] for row in duo},
                         {tp.id: tp.sc_calendar_color, tp2.id: tp2.sc_calendar_color})
        self.assertEqual(rows['SC 1605 Nobody']['extendedProps']['staff'], [])
        # Stable across users and sessions.
        self._login_tp()
        self.assertEqual(self._feed()['SC 1605 Solo']['extendedProps']['staff'][0]['color'],
                         tp.sc_calendar_color)

    # -- UC-3 ------------------------------------------------------------
    def test_events_calendar_opts_in(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/events/calendar')
        node = tree.xpath('//owl-component[@name="bemade_sports_clinic.sc_calendar"]')[0]
        self.assertIs(json.loads(node.get('props')).get('staffColors'), True)

    def test_backend_user_form_has_the_colour(self):
        view = self.env.ref('base.view_users_form')
        arch = self.env['res.users'].get_view(view.id, 'form')['arch']
        self.assertIn('name="sc_calendar_color"', arch)


@tagged('post_install', '-at_install')
class TestStaffColoursTourPhone1605(Colours1605Common):
    browser_size = '390x844'

    def test_dots_and_legend_phone(self):
        self._switch(True)
        self.start_tour('/my/events/calendar', 'sc_1605_calendar_colours', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestStaffColoursTourLaptop1605(Colours1605Common):
    browser_size = '1366x768'

    def test_dots_and_legend_laptop(self):
        self._switch(True)
        self.start_tour('/my/events/calendar', 'sc_1605_calendar_colours', login='pc.tp@example.com')


@tagged('post_install', '-at_install')
class TestStaffColoursI18n1605(Colours1605Common):

    # -- UC-5 ------------------------------------------------------------
    def test_legend_terms_in_french(self):
        from odoo.tools.translate import code_translations
        messages = code_translations.get_web_translations('bemade_sports_clinic', 'fr_CA')['messages']
        french = {row['id']: row['string'] for row in messages}
        for term, translation in (('Therapists', 'Thérapeutes'),
                                  ('Unassigned', 'Non assigné'),
                                  ('Show all therapists', 'Afficher tous les thérapeutes'),
                                  ('Show only %s', 'Afficher seulement %s')):
            self.assertEqual(french.get(term), translation, term)
