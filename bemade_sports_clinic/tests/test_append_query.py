from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_sports_clinic.controllers.task_management_portal import (
    _append_query,
)


@tagged("-at_install", "post_install")
class TestAppendQuery(TransactionCase):
    """Fragment-safe redirect params (candidate human-test finding 2026-07-10:
    '&success=' appended AFTER '#activities' broke the tab anchor, dumping the
    user on the first tab after adding an activity)."""

    def test_fragment_preserved(self):
        self.assertEqual(
            _append_query('/my/player?player_id=7#activities', 'success=activity_created'),
            '/my/player?player_id=7&success=activity_created#activities')

    def test_no_fragment(self):
        self.assertEqual(
            _append_query('/my/activities', 'error=missing_fields'),
            '/my/activities?error=missing_fields')

    def test_no_query_yet_with_fragment(self):
        self.assertEqual(
            _append_query('/my/player#activities', 'team_id=7'),
            '/my/player?team_id=7#activities')
