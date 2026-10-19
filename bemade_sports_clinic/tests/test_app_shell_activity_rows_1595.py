"""Task 1595 (portal app P3) — activity rows show their type and a link to
their related record; the activity page shows its creation date.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-1 An activity row (/my/activities, team / player Activities tabs) is a
  link row (sc_link_row): the title opens the activity, the subtitle shows
  the activity TYPE when a summary is the title, and the related record
  — player (« Last, First »), team or event — is a separate link to that
  record's page. Never an <a> inside an <a>.
* UC-2 An activity about an injury (task 1409's ``injury_id``) also links
  to the injury page.
* UC-3 No link when the viewer may not open the record: a coach never gets
  a link to (nor the diagnosis of) an injury hidden from coaches; a related
  record whose page refuses the viewer is plain text (the activity's own
  ``res_name``), never a link.
* UC-4 The activity page shows « Créée le » (creation date + time) and the
  related record through the same access-gated links.
* UC-5 French (fr_CA): « Créée le » and the related-record label render
  translated.
"""
from unittest.mock import patch

from lxml import html as lxml_html

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.controllers.access_control_mixin import AccessControlMixin
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


def _text(node):
    return ' '.join(node.text_content().split())


class _ActivityRowsMixin:

    @staticmethod
    def _row(tree, activity):
        rows = tree.xpath('//section[@data-sc-tab-panel="all"]//*[@data-sc-activity-row="%s"]'
                          % activity.id) or tree.xpath('//*[@data-sc-activity-row="%s"]' % activity.id)
        return rows[0] if rows else None

    @staticmethod
    def _related(row):
        return [(a.get('data-sc-row-link'), a.get('href'), _text(a))
                for a in row.xpath('.//a[contains(@class, "o_sc_row_link")]')]


@tagged('post_install', '-at_install')
class TestAppShellActivityRows1595(_ActivityRowsMixin, AppShellCommon):

    # -- UC-1 ------------------------------------------------------------
    def test_row_type_and_related_links(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/activities')
        expected = {
            self.act_player: ('sports.patient', '/my/player?player_id=%s' % self.player.id, 'One, Pat'),
            self.act_team: ('sports.team', '/my/team?team_id=%s' % self.team_a.id, 'PC Team A'),
            self.act_event: ('sports.event', '/my/event/%s' % self.event.id, self.event.display_name),
        }
        for activity, link in expected.items():
            row = self._row(tree, activity)
            self.assertIsNotNone(row, activity.summary)
            main = row.xpath('.//a[contains(@class, "o_sc_link_row_main")]')
            self.assertEqual(len(main), 1, activity.summary)
            self.assertEqual(main[0].get('href'), '/my/activity/%s' % activity.id)
            self.assertEqual(_text(main[0]), activity.summary)
            # The type, now that the summary is the title.
            self.assertEqual(row.xpath('string(.//*[contains(@class, "o_sc_activity_type")])'),
                             activity.activity_type_id.name)
            self.assertEqual(self._related(row), [link], activity.summary)
            # No nested anchors anywhere in the row.
            self.assertFalse(row.xpath('.//a//a'), activity.summary)

    def test_title_is_the_type_without_summary(self):
        self.act_team.summary = False
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/activities')
        row = self._row(tree, self.act_team)
        self.assertEqual(_text(row.xpath('.//a[contains(@class, "o_sc_link_row_main")]')[0]),
                         self.act_team.activity_type_id.name)
        # Not repeated in the subtitle.
        self.assertFalse(row.xpath('.//*[contains(@class, "o_sc_activity_type")]'))

    def test_team_and_player_tabs_use_link_rows(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/team?team_id=%s&tab=activities' % self.team_a.id)
        row = self._row(tree, self.act_team)
        self.assertEqual(self._related(row)[0][1], '/my/team?team_id=%s' % self.team_a.id)
        _text_, tree = self._get('/my/player?player_id=%s&tab=activities' % self.player.id)
        row = self._row(tree, self.act_player)
        self.assertEqual(self._related(row)[0][1], '/my/player?player_id=%s' % self.player.id)
        self.assertFalse(tree.xpath('//*[@data-sc-activity-row]//a//a'))

    # -- UC-2 ------------------------------------------------------------
    def test_injury_activity_links_the_injury(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/activities')
        row = self._row(tree, self.act_injury)
        self.assertEqual(self._related(row), [
            ('sports.patient', '/my/player?player_id=%s' % self.player.id, 'One, Pat'),
            # Task 1616: the injury's open card (no injury page any more).
            ('sports.patient.injury', '/my/player?player_id=%s&tab=injuries&injury=%s#injury-%s' % (
                self.player.id, self.injury.id, self.injury.id), 'Sprain'),
        ])

    # -- UC-3 ------------------------------------------------------------
    def test_coach_gets_no_link_to_hidden_injury(self):
        self.injury.sudo().hidden_from_coaches = True
        self.act_injury.user_id = self.coach
        self._switch(True)
        self._login_coach()
        _text_, tree = self._get('/my/activities')
        row = self._row(tree, self.act_injury)
        self.assertIsNotNone(row)
        self.assertEqual(self._related(row), [
            ('sports.patient', '/my/player?player_id=%s' % self.player.id, 'One, Pat')])
        self.assertFalse(row.xpath('.//*[@data-sc-row-link-plain="sports.patient.injury"]'))
        self.assertNotIn('/my/injury/edit', lxml_html.tostring(row).decode())

    def test_refused_record_is_plain_text(self):
        self._switch(True)
        self._login_tp()
        with patch.object(AccessControlMixin, '_check_access_to_patient',
                          side_effect=AccessError('refused')):
            _text_, tree = self._get('/my/activities')
        row = self._row(tree, self.act_player)
        self.assertEqual(self._related(row), [])
        plain = row.xpath('.//*[@data-sc-row-link-plain="sports.patient"]')
        self.assertEqual(len(plain), 1)
        self.assertEqual(_text(plain[0]), self.act_player.res_name)
        self.assertNotIn('/my/player?player_id=', lxml_html.tostring(row).decode())

    # -- UC-4 ------------------------------------------------------------
    def test_detail_creation_date_and_related(self):
        self._switch(True)
        self._login_tp()
        _text_, tree = self._get('/my/activity/%s' % self.act_injury.id)
        created = tree.xpath('//*[@data-sc-activity-created]')
        self.assertEqual(len(created), 1)
        self.assertIn(str(self.act_injury.create_date.year), _text(created[0]))
        dt = created[0].xpath('ancestor::dd[1]/preceding-sibling::dt[1]')[0]
        self.assertEqual(_text(dt), 'Created')
        related = tree.xpath('//*[@data-sc-section="activity.related"]//a/@href')
        self.assertEqual(related, ['/my/player?player_id=%s' % self.player.id,
                                   '/my/player?player_id=%s&tab=injuries&injury=%s#injury-%s' % (
                                       self.player.id, self.injury.id, self.injury.id)])
        # The sheets still return to the related record.
        form = tree.xpath('//dialog[@id="sc_activity_complete_sheet"]//form')[0]
        self.assertEqual(form.xpath('.//input[@name="return_url"]/@value'),
                         ['/my/player?player_id=%s' % self.player.id])


@tagged('post_install', '-at_install')
class TestAppShellActivityRowsI18n1595(_ActivityRowsMixin, TestAppShellI18n1538):

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None
    test_players_sort_switch_in_french = test_contact_practice_in_french = None

    def test_detail_in_french(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr('/my/activity/%s' % self.act_player.id))
        terms = [_text(dt) for dt in tree.xpath('//*[@data-sc-section="activity.detail"]//dt')]
        self.assertIn('Créée le', terms)
        self.assertIn('Enregistrement associé', terms)
