# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Hook 2 — nav entries and ``pk_visible_nav``. Synthetic entries only.

Acceptance criteria:

* UC-K9 ``pk_visible_nav(roles, placement, ctx)`` returns the entries of
  ``_pk_nav()`` declared at ``placement`` and visible to ``roles`` (include /
  exclude, exclude wins), ordered by ``sequence`` — not by declaration order.
* UC-K10 An entry's ``requires(ctx)`` gates it (a feature flag supplied by
  the caller's context); no ``requires`` = always.
* UC-K11 ``pk_nav(...)`` builds the entry shape the shell renders (key,
  label, icon, url, include, exclude, requires, placement, sequence,
  subtitle); ``pk_nav_label(key)`` / ``pk_nav_labels()`` give the labels,
  an unknown key raises.
* UC-K12 A consumer appends its own entry through ``super()``; an entry
  re-declared under an existing key replaces it in place.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tools import pk_nav

from .common import pk_hook

BOTH = ('tab', 'rail')
PLUS = ('plus',)


def _entries():
    return [
        pk_nav('kit_three', 'Three', 'more', '/kit/3', {'kit_a', 'kit_b'}, 30, BOTH),
        pk_nav('kit_one', 'One', 'teams', '/kit/1', {'kit_a'}, 10, BOTH, subtitle='First'),
        pk_nav('kit_two', 'Two', 'players', '/kit/2', {'kit_a', 'kit_b'}, 20, BOTH,
               exclude={'kit_b'}),
        pk_nav('kit_plus', 'Plus only', 'more', '/kit/p', {'kit_a', 'kit_b'}, 40, PLUS),
        pk_nav('kit_flag', 'Flagged', 'more', '/kit/f', {'kit_a'}, 15, BOTH,
               requires=lambda ctx: bool(ctx.get('kit_flag'))),
    ]


@tagged('post_install', '-at_install')
class TestPkNav(TransactionCase):

    def setUp(self):
        super().setUp()
        self.kit = self.env['portal.kit']
        self.enterContext(pk_hook(self.env, '_pk_nav', lambda _orig: _entries()))

    def _keys(self, roles, placement, ctx=None):
        return [entry['key'] for entry in self.kit.pk_visible_nav(roles, placement, ctx)]

    # -- UC-K9 ------------------------------------------------------------
    def test_filter_and_order(self):
        self.assertEqual(self._keys({'kit_a'}, 'tab'), ['kit_one', 'kit_two', 'kit_three'])
        self.assertEqual(self._keys({'kit_b'}, 'tab'), ['kit_three'])
        self.assertEqual(self._keys({'kit_a', 'kit_b'}, 'rail'), ['kit_one', 'kit_three'])
        self.assertEqual(self._keys({'kit_a'}, 'plus'), ['kit_plus'])
        self.assertEqual(self._keys(frozenset(), 'tab'), [])
        self.assertEqual(self._keys({'kit_a'}, 'nowhere'), [])

    # -- UC-K10 -----------------------------------------------------------
    def test_requires_gates_on_ctx(self):
        self.assertNotIn('kit_flag', self._keys({'kit_a'}, 'tab'))
        self.assertNotIn('kit_flag', self._keys({'kit_a'}, 'tab', {'kit_flag': False}))
        self.assertEqual(self._keys({'kit_a'}, 'tab', {'kit_flag': True}),
                         ['kit_one', 'kit_flag', 'kit_two', 'kit_three'])

    # -- UC-K11 -----------------------------------------------------------
    def test_entry_shape(self):
        entry = pk_nav('kit_x', 'X', 'icon', '/x', ['kit_a'], 5, BOTH)
        self.assertEqual(set(entry), {'key', 'label', 'icon', 'url', 'include', 'exclude',
                                      'requires', 'placement', 'sequence', 'subtitle'})
        self.assertEqual(entry['include'], frozenset({'kit_a'}))
        self.assertEqual(entry['exclude'], frozenset())
        self.assertEqual(entry['placement'], BOTH)
        self.assertIsNone(entry['requires'])
        self.assertIsNone(entry['subtitle'])

    def test_labels(self):
        self.assertEqual(str(self.kit.pk_nav_label('kit_one')), 'One')
        labels = self.kit.pk_nav_labels()
        self.assertEqual(labels['kit_plus'], 'Plus only')
        self.assertEqual(set(labels), {'kit_one', 'kit_two', 'kit_three', 'kit_plus', 'kit_flag'})
        with self.assertRaises(KeyError):
            self.kit.pk_nav_label('kit_none')

    def test_rendered_entries_are_copies(self):
        """The cached registry is shared: callers get read-only entries."""
        entry = self.kit.pk_visible_nav({'kit_a'}, 'tab')[0]
        with self.assertRaises(TypeError):
            entry['label'] = 'changed'
        self.assertEqual(dict(entry)['key'], 'kit_one')

    # -- UC-K12 -----------------------------------------------------------
    def test_consumer_appends_and_replaces(self):
        def extend(orig):
            return list(orig) + [
                pk_nav('kit_new', 'New', 'more', '/kit/n', {'kit_b'}, 25, BOTH),
                pk_nav('kit_three', 'Three again', 'more', '/kit/3b', {'kit_b'}, 5, BOTH),
            ]

        with pk_hook(self.env, '_pk_nav', extend):
            self.assertEqual(self._keys({'kit_b'}, 'tab'), ['kit_three', 'kit_new'])
            self.assertEqual(str(self.kit.pk_nav_label('kit_three')), 'Three again')
            keys = [entry['key'] for entry in self.kit.pk_nav_entries()]
            self.assertEqual(keys.count('kit_three'), 1)
            self.assertEqual(keys.index('kit_three'), 0, 'replaced in place')
