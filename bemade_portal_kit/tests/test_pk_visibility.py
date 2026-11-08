# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Hook 3 — visibility keys and ``pk_can``. Synthetic keys only.

Acceptance criteria:

* UC-K6 ``pk_is_visible(spec, roles)``: ``include`` any-of AND ``exclude``
  none-of; exclude wins.
* UC-K7 ``pk_can(key, roles)`` answers from ``_pk_visibility()``; an unknown
  key raises ``KeyError`` (a typo fails loudly, it never silently hides).
* UC-K8 ``is_system=True`` also opens the keys flagged ``'system': True``,
  whatever the roles — unless one of the roles is excluded; it never opens an
  unflagged key.
"""
from odoo.tests import TransactionCase, tagged

from .common import pk_hook

KEYS = {
    'kit.section': {'include': frozenset({'kit_a', 'kit_b'})},
    'kit.a_not_b': {'include': frozenset({'kit_a'}), 'exclude': frozenset({'kit_b'})},
    'kit.action': {'include': frozenset({'kit_b'}), 'system': True},
    'kit.action_no_a': {'include': frozenset({'kit_b'}), 'exclude': frozenset({'kit_a'}),
                        'system': True},
    'kit.field': {'include': frozenset({'kit_b'}), 'model': 'res.partner', 'field': 'comment'},
}


@tagged('post_install', '-at_install')
class TestPkVisibility(TransactionCase):

    def setUp(self):
        super().setUp()
        self.kit = self.env['portal.kit']
        self.enterContext(pk_hook(self.env, '_pk_visibility', lambda _orig: KEYS))

    # -- UC-K6 ------------------------------------------------------------
    def test_is_visible_include_exclude(self):
        spec = KEYS['kit.a_not_b']
        self.assertTrue(self.kit.pk_is_visible(spec, {'kit_a'}))
        self.assertFalse(self.kit.pk_is_visible(spec, {'kit_a', 'kit_b'}), 'exclude wins')
        self.assertFalse(self.kit.pk_is_visible(spec, {'kit_c'}))
        self.assertFalse(self.kit.pk_is_visible(spec, None))
        self.assertFalse(self.kit.pk_is_visible({}, {'kit_a'}), 'no include = nobody')

    # -- UC-K7 ------------------------------------------------------------
    def test_can_answers_from_the_hook(self):
        self.assertTrue(self.kit.pk_can('kit.section', frozenset({'kit_a'})))
        self.assertTrue(self.kit.pk_can('kit.section', frozenset({'kit_b'})))
        self.assertFalse(self.kit.pk_can('kit.section', frozenset({'kit_c'})))
        self.assertFalse(self.kit.pk_can('kit.a_not_b', frozenset({'kit_a', 'kit_b'})))
        self.assertTrue(self.kit.pk_can('kit.field', frozenset({'kit_b'})))
        self.assertEqual(set(self.kit.pk_visibility()), set(KEYS))

    def test_unknown_key_raises(self):
        with self.assertRaises(KeyError):
            self.kit.pk_can('kit.no_such_key', frozenset({'kit_a'}))

    # -- UC-K8 ------------------------------------------------------------
    def test_system_opens_flagged_keys_only(self):
        self.assertFalse(self.kit.pk_can('kit.action', frozenset({'kit_c'})))
        self.assertTrue(self.kit.pk_can('kit.action', frozenset({'kit_c'}), is_system=True))
        self.assertTrue(self.kit.pk_can('kit.action', frozenset(), is_system=True))
        # Not flagged: is_system changes nothing.
        self.assertFalse(self.kit.pk_can('kit.field', frozenset({'kit_a'}), is_system=True))

    def test_exclude_still_wins_for_system(self):
        self.assertFalse(self.kit.pk_can('kit.action_no_a', frozenset({'kit_a'}), is_system=True))
        self.assertTrue(self.kit.pk_can('kit.action_no_a', frozenset({'kit_c'}), is_system=True))
