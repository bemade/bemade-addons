# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5): the stored data moves (``tools/data_moves.py``).

* UC-M1 A column is renamed in place (every row keeps its value) with its
  field row; when the new column exists already, the old values are copied
  over it and the old column is dropped. A second run is a no-op.
* UC-M2 Parameters: copied to the new key (a set new key wins), the old one
  deleted; an absent old key leaves the new one absent. A second run is a
  no-op.
* UC-M3 A model is renamed in place (table, ``ir_model``, its fields'
  model, its external ids under the kit); when the new table exists, the
  rows missing by key are copied. A second run is a no-op.
Synthetic tables, rows and keys only.
"""
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tools import data_moves


@tagged('post_install', '-at_install')
class TestPkDataMoves(TransactionCase):

    def _columns(self, table):
        self.env.cr.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table,))
        return {row[0] for row in self.env.cr.fetchall()}

    def test_columns_rename_and_merge(self):
        cr = self.env.cr
        cr.execute("CREATE TABLE pk_t_moves (id serial PRIMARY KEY, old_a varchar, old_b boolean, new_b boolean)")
        cr.execute("INSERT INTO pk_t_moves (old_a, old_b, new_b) VALUES ('light', true, false), ('dark', NULL, true)")
        mapping = (('pk_t_moves', 'old_a', 'new_a', 'pk.t.moves', 'pk_t_module'),
                   ('pk_t_moves', 'old_b', 'new_b', 'pk.t.moves', 'pk_t_module'))
        moved = data_moves.move_columns(cr, mapping)
        self.assertEqual(len(moved), 2)
        self.assertEqual(self._columns('pk_t_moves'), {'id', 'new_a', 'new_b'})
        cr.execute("SELECT new_a, new_b FROM pk_t_moves ORDER BY id")
        self.assertEqual(cr.fetchall(), [('light', True), ('dark', True)], 'old values win, NULL keeps the new')
        self.assertEqual(data_moves.move_columns(cr, mapping), [], 'idempotent')

    def test_user_columns_merge(self):
        """The real mapping on res_users: an old column re-created next to
        the kit's is merged into it, the user's values kept."""
        cr = self.env.cr
        user = self.env['res.users'].create({'name': 'Pk Moves', 'login': 'pk_t_moves'})
        cr.execute("ALTER TABLE res_users ADD COLUMN sc_theme varchar, ADD COLUMN sc_show_done_buttons boolean")
        cr.execute("UPDATE res_users SET sc_theme = 'dark', sc_show_done_buttons = true WHERE id = %s", (user.id,))
        data_moves.move_columns(cr)
        self.assertNotIn('sc_theme', self._columns('res_users'))
        cr.execute("SELECT pk_theme, pk_show_done_buttons FROM res_users WHERE id = %s", (user.id,))
        self.assertEqual(cr.fetchone(), ('dark', True))
        self.assertEqual(data_moves.move_columns(cr), [])

    def test_params(self):
        params = self.env['ir.config_parameter'].sudo()
        mapping = (('pk_t.old_on', 'pk_t.new_on'), ('pk_t.old_absent', 'pk_t.new_absent'),
                   ('pk_t.old_both', 'pk_t.new_both'))
        params.set_param('pk_t.old_on', 'True')
        params.set_param('pk_t.old_both', 'old')
        params.set_param('pk_t.new_both', 'new')
        self.assertEqual(sorted(data_moves.move_params(self.env.cr, mapping)), ['pk_t.old_both', 'pk_t.old_on'])
        self.env.invalidate_all()
        self.env.registry.clear_cache()
        self.assertEqual(params.get_param('pk_t.new_on'), 'True')
        self.assertFalse(params.get_param('pk_t.old_on'))
        self.assertFalse(params.get_param('pk_t.new_absent'), 'absent stays absent')
        self.assertEqual(params.get_param('pk_t.new_both'), 'new', 'a set new key wins')
        self.assertEqual(data_moves.move_params(self.env.cr, mapping), [], 'idempotent')

    def test_model_rename(self):
        cr = self.env.cr
        cr.execute("""CREATE TABLE pk_t_old_help (id serial PRIMARY KEY, key varchar, url varchar, sequence int,
                      active bool, note varchar, create_uid int, create_date timestamp, write_uid int,
                      write_date timestamp, CONSTRAINT pk_t_old_help_key_unique UNIQUE (key))""")
        cr.execute("INSERT INTO pk_t_old_help (key, url, sequence, active, note) VALUES "
                   "('a', '/a', 1, true, 'n'), ('b', '/b', 2, false, NULL)")
        mapping = (('pk.t.old.help', 'pk.t.new.help', 'pk_t_module', (('key_unique', 'key_unique'),), ()),)
        self.assertEqual(data_moves.move_models(cr, mapping), ['pk.t.old.help'])
        cr.execute("SELECT key, url, sequence, active, note FROM pk_t_new_help ORDER BY id")
        self.assertEqual(cr.fetchall(), [('a', '/a', 1, True, 'n'), ('b', '/b', 2, False, None)])
        cr.execute("SELECT 1 FROM pg_constraint WHERE conname = 'pk_t_new_help_key_unique'")
        self.assertTrue(cr.fetchone())
        self.assertEqual(data_moves.move_models(cr, mapping), [], 'idempotent')

    def test_model_merge(self):
        cr = self.env.cr
        self.env['portal.kit.help'].create({'key': 'pk_t_kept', 'url': '/kept'})
        cr.execute("""CREATE TABLE sc_help_article (id serial PRIMARY KEY, key varchar, url varchar, sequence int,
                      active bool, note varchar, create_uid int, create_date timestamp, write_uid int,
                      write_date timestamp)""")
        cr.execute("INSERT INTO sc_help_article (key, url, sequence, active, note) VALUES "
                   "('pk_t_kept', '/old', 1, true, NULL), ('pk_t_new', '/new', 3, false, 'x')")
        data_moves.move_models(cr)
        cr.execute("SELECT key, url, active FROM portal_kit_help WHERE key LIKE 'pk_t_%%' ORDER BY key")
        self.assertEqual(cr.fetchall(), [('pk_t_kept', '/kept', True), ('pk_t_new', '/new', False)])
