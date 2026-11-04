"""Task 1614 — the team digest history expands each date in place.
Synthetic fixtures only.

Acceptance criteria covered here:

* UC-DH1 History rows: every stored snapshot is one ``<details>`` row
  (date as the title) whose body is lazy-loaded from
  ``/my/team/<t>/digest/<d>/body``; the subtitle comes from the stored
  counts for a therapist (« 2 players · 5 changes · 1 new injury »), and
  « No changes » for an empty day.
* UC-DH2 A coach's subtitle only counts what a coach may read: the stored
  counts are the therapist superset (internal notes, hidden-from-coaches
  injuries), so the coach's counts come from the coach re-gated snapshot.
* UC-DH3 Body fragment: rendered alone (no page layout, never cached), the
  restored line « Snapshot of <date> (tz) — changes over the last 24 h »,
  the same ``team_digest_render`` content as the legacy page for that role,
  player details folded under « Show details »; a coach never gets the
  internal content.
* UC-DH4 Access: a non-member gets a 403, a digest of another team a 404.
* UC-DH5 An empty day answers a fragment marked ``.o_sc_empty`` (the shell's
  lazy loader keeps it instead of « Nothing to show. »).
* UC-DH6 Dark-mode theming: the history body and the single-digest page wrap
  the Bootstrap digest in ``o_sc_legacy`` (player names were white on white);
  the single-digest page shows the restored snapshot line too.
* UC-DH7 fr_CA: the subtitle and the snapshot line come out in French.

The visual contrast and the click-through (expand → player → « Voir le
détail ») are covered by the 1614 tours and stay UNVERIFIED until the
dev-review click-through.
"""
from datetime import timedelta

from lxml import html as lxml_html

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools.misc import mute_logger

from odoo.addons.bemade_sports_clinic.tests.test_app_shell_switch_1538 import AppShellCommon
from odoo.addons.bemade_sports_clinic.tests.test_app_shell_team_changes import (
    ChangeDetailFixture,
)


class Digest1614Common(ChangeDetailFixture, AppShellCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._build_change_fixture()
        today = fields.Date.today()
        Digest = cls.env['sports.team.digest']
        cls.digest = Digest._capture_team(
            cls.team_a, fields.Datetime.now(), today, 'America/Toronto')
        cls.empty_digest = Digest.create({
            'team_id': cls.team_a.id,
            'snapshot_date': today - timedelta(days=1),
            'captured_at': fields.Datetime.now() - timedelta(days=1),
            'timezone': 'America/Toronto',
            'item_data': {'window_hours': 24, 'players': []},
        })
        cls.other_digest = Digest.create({
            'team_id': cls.team_b.id,
            'snapshot_date': today,
            'captured_at': fields.Datetime.now(),
            'item_data': {},
        })
        cls.history_url = '/my/team/%s/digest-history' % cls.team_a.id

    def _body_url(self, digest, team=None):
        return '/my/team/%s/digest/%s/body' % ((team or self.team_a).id, digest.id)

    def _rows(self, tree):
        return tree.xpath('//*[@data-sc-section="digest.history"]//details[@data-sc-digest-row]')

    def _row(self, tree, digest):
        rows = [r for r in self._rows(tree) if r.get('data-sc-digest-row') == str(digest.id)]
        self.assertEqual(len(rows), 1, digest)
        return rows[0]

    @staticmethod
    def _subtitle(row):
        return ' '.join(''.join(row.xpath('.//summary//*[contains(@class, "o_sc_row_subtitle")]'
                                          '//text()')).split())


@tagged('post_install', '-at_install')
class TestDigestHistoryInline1614(Digest1614Common):

    # -- UC-DH1 ----------------------------------------------------------
    def test_rows_expand_inline_with_stored_counts(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get(self.history_url)
        rows = self._rows(tree)
        self.assertEqual(len(rows), 2)
        row = self._row(tree, self.digest)
        self.assertEqual(row.get('data-sc-lazy-url'), self._body_url(self.digest))
        self.assertIn('o_sc_expand', row.get('class'))
        self.assertTrue(row.xpath('.//*[contains(@class, "o_sc_legacy")]'
                                  '[contains(@class, "o_sc_lazy_body")]'))
        d = self.digest
        self.assertTrue(d.player_count and d.change_count, 'fixture has changes')
        expected = ['%s player%s' % (d.player_count, '' if d.player_count == 1 else 's'),
                    '%s change%s' % (d.change_count, '' if d.change_count == 1 else 's')]
        if d.new_injury_count:
            expected.append('%s new injur%s' % (
                d.new_injury_count, 'y' if d.new_injury_count == 1 else 'ies'))
        self.assertEqual(self._subtitle(row), ' · '.join(expected))
        self.assertEqual(self._subtitle(self._row(tree, self.empty_digest)), 'No changes')
        # The day's own page stays one tap away (notifications link to it).
        self.assertEqual(row.xpath('.//a[@data-sc-digest-id]/@href'),
                         ['/my/team/%s/digest/%s' % (self.team_a.id, d.id)])

    def test_counts_label_singular_and_none(self):
        Digest = self.env['sports.team.digest']
        one = Digest.new({'player_count': 1, 'change_count': 1, 'new_injury_count': 1})
        self.assertEqual(one._sc_counts_label('tp'), '1 player · 1 change · 1 new injury')
        none = Digest.new({'player_count': 0, 'change_count': 0})
        self.assertEqual(none._sc_counts_label('tp'), 'No changes')

    # -- UC-DH2 ----------------------------------------------------------
    def test_coach_counts_are_coach_gated(self):
        tp = self.digest._sc_counts('tp')
        coach = self.digest._sc_counts('coach')
        self.assertEqual(tp, {'players': self.digest.player_count,
                              'changes': self.digest.change_count,
                              'new_injuries': self.digest.new_injury_count})
        # The hidden-from-coaches hip resolution is in the TP superset only.
        self.assertLess(coach['changes'], tp['changes'])
        self.assertEqual(coach['players'], 1)
        self._switch(True)
        self._login_coach()
        _text, tree = self._get(self.history_url)
        self.assertEqual(self._subtitle(self._row(tree, self.digest)),
                         self.digest._sc_counts_label('coach'))

    # -- UC-DH3 ----------------------------------------------------------
    def test_body_fragment(self):
        self._switch(True)
        self._login_tp()
        resp = self.url_open(self._body_url(self.digest))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.headers.get('Cache-Control'), 'no-store')
        self.assertNotIn('data-sc-app-shell', resp.text)
        self.assertNotIn('<html', resp.text.lower())
        tree = lxml_html.fromstring(resp.text)
        line = ' '.join(''.join(tree.xpath('//*[@data-sc-section="digest.snapshot"]//text()')).split())
        self.assertTrue(line.startswith('Snapshot of '), line)
        self.assertIn('(America/Toronto)', line)
        self.assertTrue(line.endswith('changes over the last 24 h'), line)
        self.assertIn('Tail', resp.text)
        self.assertIn('Synthetic hip', resp.text)
        # Player details stay folded under « Show details ».
        folded = tree.xpath('//details[contains(@class, "o_sc_card_detail")]')
        self.assertTrue(folded)
        self.assertFalse([d for d in folded if d.get('open') is not None])
        self.assertIn('Show details', resp.text)
        # Same content as the legacy page for that role.
        self._switch(False)
        legacy = self.url_open('/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id)).text
        legacy_tree = lxml_html.fromstring(legacy)
        self.assertEqual(
            ' '.join(legacy_tree.xpath('//div[contains(@class, "team-digest")]')[0]
                     .text_content().split()),
            ' '.join(tree.xpath('//div[contains(@class, "team-digest")]')[0]
                     .text_content().split()))

    def test_body_fragment_coach(self):
        self._switch(True)
        self._login_coach()
        resp = self.url_open(self._body_url(self.digest))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('Tail', resp.text)
        self.assertNotIn('Synthetic hip', resp.text)
        self.assertNotIn('Synthetic secret', resp.text)

    # -- UC-DH4 ----------------------------------------------------------
    @mute_logger('odoo.http')
    def test_body_fragment_access(self):
        self._switch(True)
        self._login_plain()
        self.assertEqual(self.url_open(self._body_url(self.digest)).status_code, 403)
        self._login_tp()
        self.assertEqual(
            self.url_open(self._body_url(self.other_digest)).status_code, 404)
        self.assertEqual(
            self.url_open(self._body_url(self.other_digest, self.team_b)).status_code, 403)

    # -- UC-DH5 ----------------------------------------------------------
    def test_empty_day_fragment(self):
        self._switch(True)
        self._login_coach()
        resp = self.url_open(self._body_url(self.empty_digest))
        self.assertEqual(resp.status_code, 200)
        tree = lxml_html.fromstring(resp.text)
        self.assertTrue(tree.xpath('//*[contains(@class, "o_sc_empty")]'))
        self.assertIn('No changes were recorded for this day.', resp.text)

    # -- UC-DH6 ----------------------------------------------------------
    def test_single_digest_page_is_themed(self):
        self._switch(True)
        self._login_tp()
        _text, tree = self._get('/my/team/%s/digest/%s' % (self.team_a.id, self.digest.id))
        body = tree.xpath('//*[@data-sc-section="digest.body"]')
        self.assertTrue(body)
        self.assertIn('o_sc_legacy', body[0].get('class'))
        line = ' '.join(''.join(tree.xpath('//*[@data-sc-section="digest.snapshot"]//text()')).split())
        self.assertTrue(line.startswith('Snapshot of '), line)
        self.assertIn('(America/Toronto)', line)


@tagged('post_install', '-at_install')
class TestDigestHistoryInlineFr1614(Digest1614Common):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        env['res.lang']._activate_lang('fr_CA')
        env['ir.module.module']._load_module_terms(
            ['bemade_sports_clinic'], ['fr_CA'], overwrite=True)
        if env['ir.module.module']._get('website').state == 'installed':
            fr_lang = env['res.lang']._lang_get('fr_CA')
            for website in env['website'].sudo().search([]):
                website.language_ids = [Command.link(fr_lang.id)]
        cls.tp.write({'lang': 'fr_CA'})

    def _fr(self, url):
        self.opener.cookies.set('frontend_lang', 'fr_CA')
        resp = self.url_open(url)
        self.assertEqual(resp.status_code, 200, url)
        return resp.text

    # -- UC-DH7 ----------------------------------------------------------
    def test_french(self):
        self._switch(True)
        self._login_tp()
        tree = lxml_html.fromstring(self._fr(self.history_url))
        subtitle = self._subtitle(self._row(tree, self.digest))
        self.assertIn('joueur', subtitle)
        self.assertIn('changement', subtitle)
        self.assertEqual(self._subtitle(self._row(tree, self.empty_digest)), 'Aucun changement')
        self.assertIn('Ouvrir cette journée', self._fr(self.history_url))
        text = self._fr(self._body_url(self.digest))
        tree = lxml_html.fromstring(text)
        line = ' '.join(''.join(tree.xpath('//*[@data-sc-section="digest.snapshot"]//text()')).split())
        self.assertTrue(line.startswith('Instantané du '), line)
        self.assertTrue(line.endswith('changements des dernières 24 h'), line)
