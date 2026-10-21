"""Team page (app shell) — recent changes carry the legacy card's content.

Owner review 2026-10-11: the original portal's recent-changes card was nicer
(the ⚡ « Changements récents » pill) and the shell must show ALL the same
information. Synthetic fixtures.

Acceptance criteria:

* UC-RC1 A changed player's row carries the yellow ⚡ « Recent changes » pill
  instead of the mauve « New » chip, next to its status pills (UC-RC9).
* UC-RC2 A changed player whose removal is pending shows « Removal pending »
  on the row, as the legacy card's strip did.
* UC-RC3 Opening a changed row loads the legacy card's whole detail
  (owner layout 2026-10-11): training recommendation, predicted return
  (injured player), last consultation, the ⚡-headed list of NON-injury
  changes, then « Active injuries » (diagnosis, dates, notes, « New » /
  « Recent change » flags) with each injury's own changes inside its card.
* UC-RC10 Every injury change sits in its injury's card, never in the general
  list; active injuries are ordered most recently changed first (unchanged
  ones last); a resolved injury with changes in the window gets its own card
  under « Resolved injuries », a resolved one without changes is not shown;
  only cards with changes carry the ⚡ « Recent change » flag.
* UC-RC12 (owner 2026-10-11, « Kara ») « Recent changes » lists only players
  with something to show (the same presence rule as the ⚡ pill): a player
  whose activity stamp is in the window but whose changes net to nothing
  moves to « Other players to watch » when red or yellow, and is not listed
  at all when green.
* UC-AN1 (owner 2026-10-11) The team announcement is a labelled section
  (« TEAM ANNOUNCEMENT », like « RECENT CHANGES ») whose header carries the
  « History » link — always, with or without a standing announcement, for
  therapists and coaches; its sheet shows an empty state when there is no
  history. The card is an edit card: ONE pencil reveals the compose form
  (hidden by default) and an archive ICON (no text) sits next to it, both
  for an announcement author only; the archive icon only when there is an
  announcement to archive.
* UC-RC11 A coach never sees a hidden-from-coaches injury (even resolved with
  changes) nor any injury's internal notes in the detail.
* UC-RC4 A coach's detail never carries an injury's internal notes; a
  therapist's does.
* UC-RC5 The legacy card's lazy fragment (no ``detail``) is unchanged: the
  change list only, no injury block.
* UC-RC6 The pills, injury count and the detail render in French (fr_CA).
* UC-RC7 (owner 2026-10-11) Every player row shows the active-injury count
  the legacy card carried (⛓ n): team page recent changes, players to watch,
  roster, and the players list. A player with no active injury shows none.
* UC-RC8 The players list flags a changed player with the same ⚡ pill, not a
  mauve « New » chip.
* UC-RC9 (owner 2026-10-11) Every player row shows the legacy card's distinct
  Match and Practice pills (✓ green / ⚠ yellow « no contact » / ⊘ red) in
  place of the combined stage chip, on the team page and the players list.
"""
from datetime import date, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import tagged

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_i18n_1538 import TestAppShellI18n1538
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon


@tagged('post_install', '-at_install')
class TestAppShellTeamChanges(AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        now = fields.Datetime.now()
        cls.player.sudo().write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': now,
            'match_status': 'no', 'practice_status': 'no',
            'training_recommendation': 'Synthetic bike only',
            'predicted_return_date': date(2030, 1, 15),
            'last_consultation_date': date(2026, 1, 10),
        })
        cls.injury.sudo().write({
            'external_notes': 'Synthetic external note',
            'internal_notes': 'Synthetic internal note',
        })
        cls.url = '/my/team?team_id=%s' % cls.team_a.id

    def _presence(self, injuries=()):
        return patch.object(
            type(self.env['sports.patient']), '_dashboard_card_presence',
            return_value={'players': {self.player.id}, 'injuries': set(injuries)})

    def _injury_presence(self, injuries=()):
        return patch.object(
            type(self.env['sports.patient']), '_dashboard_injury_presence',
            return_value=set(injuries))

    def _changed_row(self, tree):
        rows = tree.xpath('//*[@data-sc-section="team.recent_changes"]'
                          '//*[contains(@class, "o_sc_player_row")][@data-sc-player-id="%s"]'
                          % self.player.id)
        self.assertEqual(len(rows), 1)
        return rows[0]

    def _detail(self, injuries=()):
        with self._presence(injuries), self._injury_presence(injuries):
            _text, tree = self._get(self.url)
            # Task 1626: the lazy URL is on the row's « Details » region.
            url = self._changed_row(tree).xpath('.//*[@data-sc-row-detail]/@data-sc-lazy-url')[0]
            text, tree = self._get(url)
        return url, text, tree

    # -- UC-RC1 ----------------------------------------------------------
    def test_changed_row_keeps_status_chip_and_bolt_pill(self):
        self._switch(True)
        self._login_tp()
        with self._presence():
            _text, tree = self._get(self.url)
        row = self._changed_row(tree)
        self.assertFalse(row.xpath('.//*[contains(@class, "o_sc_chip_mauve")]'))
        pill = row.xpath('.//*[contains(@class, "o_sc_recent_pill")]')
        self.assertEqual(len(pill), 1)
        self.assertTrue(pill[0].xpath('.//i[contains(@class, "fa-bolt")]'))
        self.assertIn('Recent changes', pill[0].text_content())

    # -- UC-RC2 ----------------------------------------------------------
    def test_changed_row_shows_pending_removal(self):
        self.player.sudo().write({'pending_removal': True})
        self._switch(True)
        self._login_tp()
        with self._presence():
            _text, tree = self._get(self.url)
        self.assertIn('Removal pending', self._changed_row(tree).text_content())

    # -- UC-RC3 ----------------------------------------------------------
    def test_detail_carries_legacy_card_content_in_order(self):
        self._switch(True)
        self._login_tp()
        url, text, tree = self._detail(injuries={self.injury.id})
        self.assertIn('detail=1', url)
        body = ' '.join(tree.text_content().split()).lower()
        expected = ['synthetic bike only', '2030', 'last consultation', 'active injuries', 'sprain']
        positions = [body.find(s) for s in expected]
        self.assertNotIn(-1, positions, body)
        self.assertEqual(positions, sorted(positions), body)
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_injury_new")]'))
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_injury_changed")]'))
        self.assertIn('synthetic external note', body)
        # The notes changes live inside the Sprain card, not a general list.
        card = tree.xpath('//*[contains(@class, "o_sc_injury_detail")]')[0]
        self.assertTrue(card.xpath('.//*[contains(@class, "dashboard-digest-item")]'))
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_recent_changes_content")]'))

    # -- UC-RC4 ----------------------------------------------------------
    def test_detail_internal_notes_role_scoped(self):
        self._switch(True)
        self._login_tp()
        _url, text, _tree = self._detail()
        self.assertIn('Synthetic internal note', text)
        self._login_coach()
        _url, text, _tree = self._detail()
        self.assertIn('Synthetic external note', text)
        self.assertNotIn('Synthetic internal note', text)

    # -- UC-RC5 ----------------------------------------------------------
    def test_legacy_fragment_unchanged(self):
        self._login_tp()
        text, tree = self._get('/my/player/%s/recent-changes' % self.player.id)
        self.assertFalse(tree.xpath('//*[contains(@class, "o_sc_injury_detail")]'))
        self.assertNotIn('Synthetic bike only', text)

    # -- UC-RC7 ----------------------------------------------------------
    def _counts(self, tree, section):
        return {
            int(node.get('data-sc-player-id')): [
                ' '.join(c.text_content().split())
                for c in node.xpath('.//*[contains(@class, "o_sc_injury_count")]')]
            for node in tree.xpath('//*[@data-sc-section="%s"]//*[@data-sc-player-id]' % section)}

    def test_rows_show_injury_count(self):
        healthy = self.env['sports.patient'].create({
            'first_name': 'Hal', 'last_name': 'Healthy',
            'team_ids': [fields.Command.set([self.team_a.id])],
        })
        self._switch(True)
        self._login_tp()
        with self._presence():
            _text, tree = self._get(self.url)
        self.assertEqual(self._counts(tree, 'team.recent_changes')[self.player.id], ['1'])
        self.assertEqual(self._counts(tree, 'team.roster')[self.player.id], ['1'])
        self.assertEqual(self._counts(tree, 'team.roster')[healthy.id], [])
        _text, tree = self._get('/my/players')
        self.assertEqual(self._counts(tree, 'players.list')[self.player.id], ['1'])
        self.assertEqual(self._counts(tree, 'players.list')[healthy.id], [])

    def test_watchlist_row_shows_injury_count(self):
        self.player.sudo().write({'dashboard_last_activity_tp': False,
                                  'dashboard_last_activity_coach': False})
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.url)
        self.assertEqual(self._counts(tree, 'team.watchlist')[self.player.id], ['1'])

    # -- UC-RC8 ----------------------------------------------------------
    def test_players_list_changed_row_uses_bolt_pill(self):
        self._switch(True)
        self._login_tp()
        with self._presence():
            _text, tree = self._get('/my/players')
        row = tree.xpath('//*[@data-sc-section="players.list"]//*[@data-sc-player-id="%s"]'
                         % self.player.id)[0]
        self.assertFalse(row.xpath('.//*[contains(@class, "o_sc_chip_mauve")]'))
        self.assertTrue(row.xpath('.//*[contains(@class, "o_sc_recent_pill")]//i[contains(@class, "fa-bolt")]'))
    # -- UC-RC9 ----------------------------------------------------------
    def _pills(self, tree, section, player):
        node = tree.xpath('//*[@data-sc-section="%s"]//*[@data-sc-player-id="%s"]'
                          % (section, player.id))[0]
        return [(' '.join(p.text_content().split()),
                 p.get('class').split('o_sc_chip_')[1].split()[0],
                 p.xpath('./i/@class')[0])
                for p in node.xpath('.//*[contains(@class, "o_sc_status_pill")]')]

    def test_rows_show_match_and_practice_pills(self):
        yellow = self.env['sports.patient'].create({
            'first_name': 'Yan', 'last_name': 'Yellow',
            'team_ids': [fields.Command.set([self.team_a.id])],
            'match_status': 'no', 'practice_status': 'no_contact',
        })
        self._switch(True)
        self._login_coach()
        _text, tree = self._get(self.url)
        self.assertEqual(self._pills(tree, 'team.roster', self.player), [
            ('Match', 'red', 'fa fa-ban'), ('Practice', 'red', 'fa fa-ban')])
        self.assertEqual(self._pills(tree, 'team.roster', yellow), [
            ('Match', 'red', 'fa fa-ban'),
            ('Practice', 'yellow', 'fa fa-exclamation-triangle')])
        self.assertFalse(tree.xpath('//*[@data-sc-section="team.roster"]'
                                    '//*[contains(@class, "o_sc_chip")]'
                                    '[normalize-space()="Injured"]'))
        _text, tree = self._get('/my/players')
        self.assertEqual(self._pills(tree, 'players.list', yellow), [
            ('Match', 'red', 'fa fa-ban'),
            ('Practice', 'yellow', 'fa fa-exclamation-triangle')])
        healthy = self.env['sports.patient'].create({
            'first_name': 'Gil', 'last_name': 'Green',
            'team_ids': [fields.Command.set([self.team_a.id])],
        })
        _text, tree = self._get(self.url)
        self.assertEqual(self._pills(tree, 'team.roster', healthy), [
            ('Match', 'green', 'fa fa-check'), ('Practice', 'green', 'fa fa-check')])
    # -- UC-RC12 ---------------------------------------------------------
    def test_stamp_without_changes_not_listed_as_changed(self):
        healthy = self.env['sports.patient'].create({
            'first_name': 'Gwen', 'last_name': 'Green',
            'team_ids': [fields.Command.set([self.team_a.id])],
        })
        now = fields.Datetime.now()
        healthy.sudo().write({'dashboard_last_activity_tp': now,
                              'dashboard_last_activity_coach': now})
        self._switch(True)
        self._login_tp()
        with patch.object(type(self.env['sports.patient']), '_dashboard_card_presence',
                          return_value={'players': set(), 'injuries': set()}):
            _text, tree = self._get(self.url)
        recent = tree.xpath('//*[@data-sc-section="team.recent_changes"]//*[@data-sc-player-id]/@data-sc-player-id')
        watch = tree.xpath('//*[@data-sc-section="team.watchlist"]//*[@data-sc-player-id]/@data-sc-player-id')
        self.assertEqual(recent, [])
        self.assertIn(str(self.player.id), watch)  # red, stamp in window
        self.assertNotIn(str(healthy.id), watch)
        self.assertTrue(tree.xpath('//*[@data-sc-section="team.recent_changes"]'
                                   '//*[contains(@class, "o_sc_empty")]'))

    # -- UC-AN1 ----------------------------------------------------------
    def _announcement(self, tree):
        area = tree.xpath('//*[@data-sc-section="team.announcement.area"]')
        self.assertEqual(len(area), 1)
        header = area[0].xpath('./h2[contains(@class, "o_sc_section_header")]')[0]
        self.assertIn('Team announcement', header.text_content())
        links = header.xpath('.//button[@data-sc-sheet-open="sc_announcement_history_sheet"]'
                             '[contains(@class, "o_sc_link_btn")]')
        self.assertEqual(len(links), 1)
        self.assertEqual(len(tree.xpath(
            '//*[@data-sc-sheet-open="sc_announcement_history_sheet"]')), 1)
        self.assertTrue(tree.xpath('//dialog[@id="sc_announcement_history_sheet"]'))
        return area[0].xpath('.//*[@data-sc-edit-card="announcement"]')[0]

    def test_announcement_section_history_pencil_archive(self):
        self._switch(True)
        self.team_a.sudo().write({'announcement': False})
        for login in (self._login_tp, self._login_coach):
            login()
            _text, tree = self._get(self.url)
            self._announcement(tree)
            self.assertTrue(tree.xpath('//dialog[@id="sc_announcement_history_sheet"]'
                                       '//*[contains(@class, "o_sc_empty")]'))
        # Therapist, no announcement: the pencil, no archive icon.
        self._login_tp()
        _text, tree = self._get(self.url)
        card = self._announcement(tree)
        self.assertEqual(len(card.xpath('.//button[@data-sc-edit-toggle]')), 1)
        self.assertFalse(card.xpath('.//*[@data-sc-section="team.announcement.archive"]'))
        edit = card.xpath('.//*[@data-sc-edit-view="edit"]')[0]
        self.assertEqual(edit.get('hidden'), 'hidden')
        self.assertEqual(edit.get('data-sc-section'), 'team.announcement.edit')
        # With an announcement: pencil + archive icon side by side.
        self.team_a.sudo().write({'announcement': 'Synthetic standing note'})
        _text, tree = self._get(self.url)
        card = self._announcement(tree)
        icons = card.xpath('.//*[contains(@class, "o_sc_card_icons")]')[0]
        self.assertEqual(len(icons.xpath('.//button[@data-sc-edit-toggle]')), 1)
        archive = icons.xpath('.//form[@data-sc-section="team.announcement.archive"]'
                              '//button[contains(@class, "o_sc_icon_btn")]')
        self.assertEqual(len(archive), 1)
        self.assertEqual(archive[0].get('aria-label'), 'Archive')
        self.assertEqual(archive[0].text_content().strip(), '')
        # Coach: neither.
        self._login_coach()
        _text, tree = self._get(self.url)
        card = self._announcement(tree)
        self.assertIn('Synthetic standing note', card.text_content())
        self.assertFalse(card.xpath('.//button[@data-sc-edit-toggle]'))
        self.assertFalse(card.xpath('.//*[@data-sc-section="team.announcement.archive"]'))


@tagged('post_install', '-at_install')
class TestAppShellTeamChangesFr(TestAppShellI18n1538):
    """UC-RC6 The pill and the detail come out in French (fr_CA)."""

    # The inherited 1538 tests run once, in their own class.
    test_home_in_french = test_teams_in_french = test_more_in_french = None

    def test_pill_and_detail_in_french(self):
        now = fields.Datetime.now()
        self.player.sudo().write({
            'dashboard_last_activity_tp': now, 'dashboard_last_activity_coach': now,
            'last_consultation_date': date(2026, 1, 10),
        })
        # A real note change, so the detail's change list has content.
        self.injury.sudo().write({'external_notes': 'Synthetic external note'})
        self.env.flush_all()
        self.env.cr.precommit.run()
        self._switch(True)
        self._login_tp()
        with patch.object(type(self.env['sports.patient']), '_dashboard_card_presence',
                          return_value={'players': {self.player.id}, 'injuries': set()}):
            text = self._fr('/my/team?team_id=%s' % self.team_a.id)
        self.assertIn('</i> Changements récents</span>', text)
        # UC-RC9's pills: label + tooltip (selection label) in French.
        # Task 1634: a therapist's card pills are the compact dropdowns
        # (short label on the face, the full value as the title).
        self.assertIn('<span class="o_sc_pill_text">Pratique</span>', text)
        self.assertIn('title="Match : Oui"', text)
        self.assertIn('title="Blessures actives"', text)
        text = self._fr('/my/player/%s/recent-changes?detail=1' % self.player.id)
        for term in ('Dernière consultation :', 'Blessures actives'):
            self.assertIn(term, text, term)


class ChangeDetailFixture:
    """One player with a player-level change, three active injuries (two
    changed at different times, one quiet), two resolved in the window (one
    hidden from coaches) and one resolved earlier. Synthetic."""

    @classmethod
    def _build_change_fixture(cls):
        env = cls.env
        cls.p = env['sports.patient'].create({
            'first_name': 'Dee', 'last_name': 'Tail',
            'team_ids': [fields.Command.set([cls.team_a.id])],
        })
        Injury = env['sports.patient.injury'].with_context(mail_notrack=True)

        def injury(diagnosis, stage='active', **vals):
            inj = Injury.create(dict(patient_id=cls.p.id, diagnosis=diagnosis, **vals))
            inj.write({'stage': stage})
            return inj.with_context(mail_notrack=False)

        cls.knee = injury('Synthetic knee', injury_date=date(2026, 3, 1))
        cls.ankle = injury('Synthetic ankle', injury_date=date(2026, 1, 1))
        cls.wrist = injury('Synthetic wrist', injury_date=date(2026, 2, 1))
        cls.shoulder = injury('Synthetic shoulder', internal_notes='Synthetic secret')
        cls.elbow = injury('Synthetic elbow', stage='resolved')
        cls.hip = injury('Synthetic hip', hidden_from_coaches=True)
        env.flush_all()
        env.cr.precommit.run()
        old = fields.Datetime.now() - timedelta(days=3)
        cls.env.cr.execute(
            "UPDATE sports_patient_injury SET create_date=%s WHERE patient_id=%s",
            (old, cls.p.id))
        env.invalidate_all()
        # Changes in the window: one player-level, the rest per injury.
        cls.p.write({'match_status': 'no'})
        cls.knee.write({'predicted_resolution_date': date(2030, 2, 1)})
        cls.ankle.write({'predicted_resolution_date': date(2030, 3, 1)})
        cls.shoulder.write({'stage': 'resolved'})
        cls.hip.write({'stage': 'resolved'})
        env.flush_all()
        env.cr.precommit.run()
        # Knee changed 5 h ago, ankle 1 h ago: ankle first.
        for inj, hours in ((cls.knee, 5), (cls.ankle, 1)):
            cls.env.cr.execute(
                "UPDATE mail_message SET date=%s WHERE model='sports.patient.injury' AND res_id=%s",
                (fields.Datetime.now() - timedelta(hours=hours), inj.id))
        env.invalidate_all()


@tagged('post_install', '-at_install')
class TestAppShellChangeDetail(ChangeDetailFixture, AppShellCommon):
    """UC-RC10 / UC-RC11 — the expanded detail's injury grouping."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_change_fixture()
        cls.url = '/my/player/%s/recent-changes?detail=1' % cls.p.id

    def _cards(self, tree):
        out = {}
        for card in tree.xpath('//*[contains(@class, "o_sc_injury_detail")]'):
            name = ' '.join(card.xpath('.//a')[0].text_content().split())
            out[name] = {
                'changed': bool(card.xpath('.//*[contains(@class, "o_sc_injury_changed")]')),
                'items': len(card.xpath('.//*[contains(@class, "dashboard-digest-item")]')),
            }
        return out

    def test_injury_changes_grouped_and_ordered(self):
        self._switch(True)
        self._login_tp()
        text, tree = self._get(self.url)
        body = ' '.join(tree.text_content().split()).lower()
        order = ['last consultation', 'active injuries', 'synthetic ankle', 'synthetic knee',
                 'synthetic wrist', 'resolved injuries', 'synthetic shoulder']
        positions = [body.find(t) for t in order]
        self.assertNotIn(-1, positions, body)
        self.assertEqual(positions, sorted(positions), body)
        self.assertNotIn('synthetic elbow', body)
        general = tree.xpath('//*[contains(@class, "o_sc_recent_changes_content")]'
                             '//*[contains(@class, "dashboard-digest-item")]')
        self.assertEqual(len(general), 1, 'only the match status change')
        self.assertLess(body.find('recent changes'), body.find('active injuries'))
        cards = self._cards(tree)
        self.assertEqual(cards['Synthetic ankle'], {'changed': True, 'items': 1})
        self.assertEqual(cards['Synthetic knee'], {'changed': True, 'items': 1})
        self.assertEqual(cards['Synthetic wrist'], {'changed': False, 'items': 0})
        self.assertTrue(cards['Synthetic shoulder']['changed'])
        self.assertTrue(cards['Synthetic hip']['changed'])
        self.assertIn('Synthetic secret', text)

    def test_coach_never_sees_hidden_or_internal(self):
        self._switch(True)
        self._login_coach()
        text, tree = self._get(self.url)
        self.assertIn('Synthetic shoulder', text)
        self.assertNotIn('Synthetic hip', text)
        self.assertNotIn('Synthetic secret', text)
