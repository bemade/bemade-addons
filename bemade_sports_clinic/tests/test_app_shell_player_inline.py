"""Player page inline editing — the separate « Edit Player » page is retired
(owner review 2026-10-10). Synthetic fixtures only.

Every field of the old edit page lives on the player page, in cards that are
read-only by default; ONE pencil per card reveals that card's autosave fields
(same /my/app/save route, roles and conflict handling), « Done » hides them
again. Play status and the training recommendation stay always live.

Acceptance criteria covered here:

* UC-1 Read mode by default: the Info tab shows the Identity, Contact,
  Medical (therapists) and Teams cards; each card's edit view is hidden and
  its read view shows the values (``data-sc-display`` hooks).
* UC-2 Edit a card: the pencil toggles the card's edit view, « Done » hides
  it; a save answers a human ``display`` string (province name, formatted
  date) so the read view updates in place — no reload (browser half: the
  ``sc_player_inline_edit`` tour).
* UC-3 Cards and roles: any staff edits Identity and Contact; Medical and
  Teams are therapist-only (a coach gets no Medical card, a read-only Teams
  card without pencil, and the server still refuses the fields: 403).
* UC-4 Always-live controls: play status and training recommendation stay
  on the Overview tab, outside any edit card.
* UC-5 Teams card: a tags field (owner review 2026-10-10, not an unbounded
  checklist) — the player's teams as removable chips + a search box over the
  teams the user may assign (a few matches at a time); each add / remove
  saves at once (browser half: the ``sc_player_teams_tags`` tour). Only the user's assignable teams are added / removed —
  the player's other teams are kept; anything else posted is ignored.
* UC-6 Header follows edits: an Identity save answers the new heading, and
  the app bar title and the hero carry ``data-sc-heading`` hooks.
* UC-7 Edit page retired: no « Edit Player » action on the player page;
  ``/my/player/edit`` redirects to the player page's Info tab, keeping the
  team / clinic context. Switch off: the legacy edit page is unchanged.
* UC-8 Emergency contacts inline: each contact card has a pencil revealing
  autosave fields (name, relationship, mobile, email); adding is an inline
  form on the Contacts tab that comes back to it; the old add / edit pages
  redirect to the Contacts tab. Coaches too (owner decision 2026-10-10):
  they see the Contacts tab with EVERY contact, add and edit them; deleting
  stays with therapists (their ACL). The coach-only primary-contact card on
  the Info tab is gone.
* UC-9 Activities follow the same UX (owner review 2026-10-10): each
  activity is ONE card with its actions inside it, and adding is an inline
  « Add Activity » card at the top of the tab (player and team pages), not a
  button opening a dialog.
* UC-10 New injury follows the same UX: no « New injury » action in the app
  bar; an inline « Add Injury » card (« Report Injury » for a coach) at the
  top of the Injuries tab — the same draft fields and create route, coming
  back to the Injuries tab; the Overview's « Active injuries » header links
  to it.
"""
from urllib.parse import parse_qs, urlparse

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon

SWITCH = 'bemade_sports_clinic.app_shell_enabled'


class PlayerInlineCommon(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['ir.config_parameter'].sudo().set_param(SWITCH, 'True')
        cls.team_c = env['sports.team'].create({'name': 'PC Team C', 'parent_id': cls.org.id})
        env['sports.team.staff'].create({
            'team_id': cls.team_c.id, 'partner_id': cls.tp.partner_id.id, 'role': 'therapist',
        })
        cls.quebec = env['res.country.state'].search([('code', '=', 'QC'), ('country_id.code', '=', 'CA')], limit=1)
        cls.player.write({'jersey_number': '12', 'position': 'Linebacker'})

    def _url(self, tab='info', **extra):
        url = '/my/player?player_id=%s&tab=%s' % (self.player.id, tab)
        for key, value in extra.items():
            url += '&%s=%s' % (key, value)
        return url

    def _save(self, record, field, value):
        record.invalidate_recordset()
        return self.url_open('/my/app/save/%s/%s' % (record._name, record.id), data={
            'field': field, 'value': value,
            'write_date': fields.Datetime.to_string(record.write_date),
            'csrf_token': self._csrf(),
        }, allow_redirects=False)

    @staticmethod
    def _card(tree, key):
        nodes = tree.xpath('//*[@data-sc-edit-card="%s"]' % key)
        return nodes[0] if nodes else None

    @staticmethod
    def _fields_in(node):
        return [props_field for props_field in node.xpath(
            './/owl-component[@name="bemade_sports_clinic.sc_autosave_field"]/@props')]


@tagged('post_install', '-at_install')
class TestPlayerInline(PlayerInlineCommon):

    # -- UC-1 ------------------------------------------------------------
    def test_info_cards_read_mode_by_default(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        for key in ('identity', 'contact', 'medical', 'teams'):
            card = self._card(tree, key)
            self.assertIsNotNone(card, key)
            edit = card.xpath('.//*[@data-sc-edit-view="edit"]')
            self.assertEqual(len(edit), 1, key)
            self.assertEqual(edit[0].get('hidden'), 'hidden', key)
            self.assertTrue(card.xpath('.//*[@data-sc-edit-view="read"]'), key)
            self.assertTrue(card.xpath('.//button[@data-sc-edit-toggle]'), key)
        # The status block was redundant with the hero and Overview (owner).
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.info.status"]'))
        identity = self._card(tree, 'identity')
        position = identity.xpath('.//*[@data-sc-display="sports.patient:%s:position"]' % self.player.id)
        self.assertEqual(position[0].text_content().strip(), 'Linebacker')

    # -- UC-2 ------------------------------------------------------------
    def test_save_answers_display(self):
        self._login_tp()
        resp = self._save(self.player, 'state_id', str(self.quebec.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['display'], self.quebec.name)
        resp = self._save(self.player, 'date_of_birth', '2010-03-04')
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertTrue(resp.json()['display'])
        self.assertNotEqual(resp.json()['display'], '2010-03-04')  # formatted for humans
        resp = self._save(self.player, 'position', '')
        self.assertEqual(resp.json()['display'], '')

    # -- UC-3 ------------------------------------------------------------
    def test_coach_cards(self):
        self._login_coach()
        _text, tree = self._get(self._url())
        for key in ('identity', 'contact'):
            self.assertTrue(self._card(tree, key).xpath('.//button[@data-sc-edit-toggle]'), key)
        self.assertIsNone(self._card(tree, 'medical'))
        teams = self._card(tree, 'teams')
        self.assertIsNotNone(teams)
        self.assertFalse(teams.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(teams.xpath('.//*[@data-sc-edit-view="edit"]'))
        with mute_logger('odoo.http'):
            for field, value in (('sc_team_ids', str(self.team_a.id)), ('allergies', 'x')):
                self.assertEqual(self._save(self.player, field, value).status_code, 403, field)

    # -- UC-4 ------------------------------------------------------------
    def test_status_and_training_stay_live(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='overview'))
        panel = tree.xpath('//*[@data-sc-tab-panel="overview"]')[0]
        live = ' '.join(self._fields_in(panel))
        self.assertIn('"sc_status"', live)
        self.assertIn('"training_recommendation"', live)
        for node in panel.xpath('.//owl-component[contains(@props, \'"sc_status"\') '
                                'or contains(@props, \'"training_recommendation"\')]'):
            self.assertFalse(node.xpath('ancestor::*[@data-sc-edit-card]'))

    # -- UC-5 ------------------------------------------------------------
    def test_teams_checklist_only_touches_assignable_teams(self):
        self.player.team_ids = [Command.set([self.team_a.id, self.team_b.id])]
        self._login_tp()
        _text, tree = self._get(self._url())
        props = ' '.join(self._fields_in(self._card(tree, 'teams')))
        self.assertIn('"sc_team_ids"', props)
        self.assertIn('"tags"', props)
        self.assertIn('PC Team C', props)
        self.assertNotIn('PC Team B', props)  # not assignable by this therapist
        # Tick C, untick A: B (not assignable) is kept.
        resp = self._save(self.player, 'sc_team_ids', '%s' % self.team_c.id)
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(set(self.player.team_ids.ids), {self.team_b.id, self.team_c.id})
        self.assertEqual(resp.json()['value'], str(self.team_c.id))
        self.assertIn('PC Team C', resp.json()['display'])
        # A non-assignable team posted is ignored.
        resp = self._save(self.player, 'sc_team_ids', '%s,%s' % (self.team_a.id, self.team_b.id))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.player.invalidate_recordset()
        self.assertEqual(set(self.player.team_ids.ids), {self.team_a.id, self.team_b.id})

    # -- UC-6 ------------------------------------------------------------
    def test_identity_save_answers_heading(self):
        self._login_tp()
        _text, tree = self._get(self._url())
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_appbar_title_text")][@data-sc-heading="title"]'))
        self.assertTrue(tree.xpath('//*[@data-sc-section="player.hero"]//*[@data-sc-heading="list_name"]'))
        resp = self._save(self.player, 'jersey_number', '7')
        self.assertEqual(resp.status_code, 200, resp.text)
        heading = resp.json()['heading']
        self.assertTrue(heading['title'].startswith('#7 '))
        self.assertIn('#7', heading['list_name'])
        self.assertIn('Linebacker', heading['context'])

    # -- UC-7 ------------------------------------------------------------
    def test_edit_page_retired(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='overview'))
        self.assertFalse(tree.xpath('//*[@data-sc-action="player.edit"]'))
        resp = self.url_open('/my/player/edit?patient_id=%s&team_id=%s' % (self.player.id, self.team_a.id),
                             allow_redirects=False)
        self.assertIn(resp.status_code, (302, 303))
        target = urlparse(resp.headers['Location'])
        args = parse_qs(target.query)
        self.assertEqual(target.path, '/my/player')
        self.assertEqual(args['player_id'], [str(self.player.id)])
        self.assertEqual(args['team_id'], [str(self.team_a.id)])
        self.assertEqual(args['tab'], ['info'])

    def test_switch_off_keeps_legacy_edit_page(self):
        self.env['ir.config_parameter'].sudo().set_param(SWITCH, False)
        self._login_tp()
        text, tree = self._get('/my/player/edit?patient_id=%s' % self.player.id)
        self.assertIsNone(self._shell(tree))
        self.assertIn('/my/player/save', text)

    # -- UC-8 ------------------------------------------------------------
    def test_contacts_inline(self):
        self._login_tp()
        _text, tree = self._get(self._url(tab='contacts'))
        card = tree.xpath('//*[@data-sc-edit-card="contact-%s"]' % self.contact.id)
        self.assertEqual(len(card), 1)
        props = ' '.join(self._fields_in(card[0]))
        for field in ('"name"', '"contact_type"', '"mobile"', '"email"'):
            self.assertIn(field, props)
        self.assertIn('"sports.patient.contact"', props)
        self.assertFalse(tree.xpath('//*[@data-sc-action="contact.edit"][@href]'))
        form = tree.xpath('//form[@data-sc-form="contact.add"]')
        self.assertEqual(len(form), 1)
        self.assertEqual(form[0].get('action'), '/my/player/contact/save')
        back = form[0].xpath('.//input[@name="return_url"]/@value')[0]
        self.assertTrue('tab=contacts' in back or back.endswith('#contacts'), back)
        for url in ('/my/player/contact/add?patient_id=%s' % self.player.id,
                    '/my/player/contact/edit?contact_id=%s' % self.contact.id):
            resp = self.url_open(url, allow_redirects=False)
            self.assertIn(resp.status_code, (302, 303), url)
            self.assertIn('tab=contacts', resp.headers['Location'], url)

    def test_contact_inline_add_round_trip(self):
        self._login_tp()
        resp = self._post_form('/my/player/contact/save', {
            'patient_id': self.player.id, 'name': 'Synthetic Guardian',
            'contact_type': 'father', 'mobile': '555-0100', 'email': '',
            'return_url': self._url(tab='contacts'),
        })
        self.assertIn(resp.status_code, (302, 303))
        location = resp.headers['Location']
        self.assertTrue('tab=contacts' in location or location.endswith('#contacts'), location)
        self.assertTrue(self.env['sports.patient.contact'].search_count(
            [('patient_id', '=', self.player.id), ('name', '=', 'Synthetic Guardian')]))

    # -- UC-9 ------------------------------------------------------------
    def test_activities_same_ux(self):
        self._login_tp()
        for url in (self._url(tab='activities'),
                    '/my/team?team_id=%s&tab=activities' % self.team_a.id):
            _text, tree = self._get(url)
            panel = tree.xpath('//section[@data-sc-tab-panel="activities"]')[0]
            add = panel.xpath('.//details[@data-sc-section="activity.add"]//form')
            self.assertEqual(len(add), 1, url)
            self.assertEqual(add[0].get('action'), '/my/activity/save', url)
            self.assertFalse(panel.xpath('.//*[@data-sc-sheet-open="sc_activity_add_sheet"]'), url)
            self.assertFalse(tree.xpath('//dialog[@id="sc_activity_add_sheet"]'), url)
            rows = panel.xpath('.//*[@data-sc-activity-row]')
            self.assertTrue(rows, url)
            for row in rows:
                self.assertIn('o_sc_card', row.get('class').split(), url)
                self.assertTrue(row.xpath('.//*[contains(@class, "o_sc_card_actions")]'
                                          '//button[@data-sc-action="activity.complete"]'), url)

    # -- UC-10 -----------------------------------------------------------
    def test_new_injury_inline(self):
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self._url(tab='injuries', team_id=self.team_a.id))
            self.assertFalse(tree.xpath('//header//*[@data-sc-action="injury.new"]'))
            panel = tree.xpath('//section[@data-sc-tab-panel="injuries"]')[0]
            card = panel.xpath('.//details[@id="sc_new_injury"][@data-sc-section="injury.new"]')
            self.assertEqual(len(card), 1)
            form = card[0].xpath('.//form[@data-sc-form="injury.new"]')[0]
            self.assertEqual(form.get('action'), '/my/patient/injury/create')
            self.assertEqual(form.get('data-sc-draft-prefix'),
                             'sports.patient.%s.new_injury.' % self.player.id)
            back = form.xpath('.//input[@name="return_url"]/@value')[0]
            self.assertIn('tab=injuries', back)
            self.assertEqual(form.xpath('.//input[@name="team_context_id"]/@value'), [str(self.team_a.id)])
            props = ' '.join(self._fields_in(form))
            self.assertIn('"diagnosis"', props)
            link = tree.xpath('//*[@data-sc-section="player.active_injuries"]//a[contains(@href, "#sc_new_injury")]')
            self.assertEqual(len(link), 1)

    def test_coach_contacts_tab(self):
        second = self.env['sports.patient.contact'].create({
            'patient_id': self.player.id, 'name': 'Synthetic Second', 'contact_type': 'father',
        })
        self._login_coach()
        _text, tree = self._get(self._url(tab='info'))
        self.assertFalse(tree.xpath('//*[@data-sc-section="player.info.emergency"]'))
        self.assertIn('contacts', tree.xpath('//nav[@data-sc-tabs]//a/@data-sc-tab'))
        _text, tree = self._get(self._url(tab='contacts'))
        for contact in (self.contact, second):
            card = tree.xpath('//*[@data-sc-edit-card="contact-%s"]' % contact.id)
            self.assertEqual(len(card), 1, contact.name)
            self.assertIn('"sports.patient.contact"', ' '.join(self._fields_in(card[0])))
            self.assertFalse(card[0].xpath('.//*[@data-sc-action="contact.delete"]'))
        self.assertTrue(tree.xpath('//form[@data-sc-form="contact.add"]'))
        resp = self._save(second, 'mobile', '555-0199')
        self.assertEqual(resp.status_code, 200, resp.text)

    def _post_form(self, url, data):
        payload = dict(data, csrf_token=self._csrf())
        return self.url_open(url, data=payload, allow_redirects=False)


@tagged('post_install', '-at_install')
class TestPlayerInlineTour(PlayerInlineCommon):

    def test_inline_edit_tour(self):
        self.start_tour(self._url(), 'sc_player_inline_edit', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.position, 'Safety')

    def test_teams_tags_tour(self):
        # The player is on A; the therapist assigns A and C: search « Team C »,
        # add it, then remove A.
        self.start_tour(self._url(), 'sc_player_teams_tags', login='pc.tp@example.com')
        self.player.invalidate_recordset()
        self.assertEqual(self.player.team_ids, self.team_c)
