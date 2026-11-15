# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5202 (kit P7): the users' layouts move with their column, byte for
byte. Synthetic layouts only.

Acceptance criteria:

* UC-M1 The former column (``sc_dashboard_layout``, the first consumer's
  field) is renamed ``pk_dashboard_layout`` in place: a stored v1 and a
  stored v2 layout are byte-identical after the move (``::text``), an
  empty one stays empty; the field's metadata and external id are this
  addon's; they load to the same normalised layout as before the move.
* UC-M2 Re-running the move is a no-op (nothing moved, values unchanged).
* UC-M3 The new column created empty first (the old one still there): the
  old values are copied over, byte for byte, and the old column dropped.
* UC-M4 The install hook runs the move and the views' adoption (a no-op
  without the consumer).
"""
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.bemade_portal_kit_dashboard import hooks
from odoo.addons.bemade_portal_kit_dashboard.tools.adopt import (
    DASH, DASH_ADOPTED_VIEWS, DASH_MOVED_COLUMNS, adopt_dashboard,
)

from .common import pk_dash_shell

OLD_MODULE = 'bemade_sports_clinic'
V1 = ('{"v": 1, "instances": [{"id": "gamma", "title": "G  one", "widget": "gamma", "enabled": true, '
      '"settings": {"size": "large", "scope_tag_ids": [3]}}, {"id": "alpha", "title": "", "widget": "alpha", '
      '"enabled": false, "settings": {}}]}')
V2 = ('{"v": 2, "instances": [{"id": "beta-2", "zone": "bottom", "title": "Bottom beta", "widget": "beta", '
      '"enabled": true, "settings": {"colors": ["blue"], "scope_tag_ids": [1, 2]}}, {"id": "gamma", '
      '"zone": "left", "title": "", "widget": "gamma", "enabled": true, "settings": {"days": 30, '
      '"size": "small", "scope_tag_ids": []}}, {"id": "later", "zone": "right", "title": "", "widget": "later", '
      '"enabled": true, "settings": {}}]}')


@tagged('post_install', '-at_install')
class TestPkDashboardMigration(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.u1 = new_test_user(cls.env, login='pk_p7_m1', groups='base.group_portal')
        cls.u2 = new_test_user(cls.env, login='pk_p7_m2', groups='base.group_portal')
        cls.u3 = new_test_user(cls.env, login='pk_p7_m3', groups='base.group_portal')

    def setUp(self):
        super().setUp()
        shell = pk_dash_shell(self.env)
        shell.__enter__()
        self.addCleanup(shell.__exit__, None, None, None)
        self.cr = self.env.cr

    def texts(self, column):
        self.cr.execute('SELECT id, %s::text FROM res_users WHERE id IN %%s ORDER BY id' % column,
                        (tuple((self.u1 | self.u2 | self.u3).ids),))
        return dict(self.cr.fetchall())

    def normalised(self, user):
        self.env.invalidate_all()
        return self.env(user=user)['portal.kit.dashboard']._pk_dash_layout()

    def as_before(self):
        """The database as the first consumer left it: the old column and
        its field row / external id, holding a v1 and a v2 layout."""
        self.env.flush_all()
        cr = self.cr
        cr.execute("UPDATE res_users SET pk_dashboard_layout = %s::jsonb WHERE id = %s", (V1, self.u1.id))
        cr.execute("UPDATE res_users SET pk_dashboard_layout = %s::jsonb WHERE id = %s", (V2, self.u2.id))
        self.env.invalidate_all()
        expected = {user.id: self.normalised(user) for user in (self.u1, self.u2, self.u3)}
        before = self.texts('pk_dashboard_layout')
        cr.execute("ALTER TABLE res_users RENAME COLUMN pk_dashboard_layout TO sc_dashboard_layout")
        cr.execute("UPDATE ir_model_fields SET name = 'sc_dashboard_layout' "
                   "WHERE model = 'res.users' AND name = 'pk_dashboard_layout' RETURNING id")
        field_id = cr.fetchone()[0]
        cr.execute("UPDATE ir_model_data SET module = %s, name = 'field_res_users__sc_dashboard_layout' "
                   "WHERE model = 'ir.model.fields' AND res_id = %s", (OLD_MODULE, field_id))
        return before, expected, field_id

    def assert_moved(self, before, expected, field_id):
        self.assertEqual(self.texts('pk_dashboard_layout'), before, 'byte-identical')
        self.cr.execute("SELECT 1 FROM information_schema.columns "
                        "WHERE table_name = 'res_users' AND column_name = 'sc_dashboard_layout'")
        self.assertFalse(self.cr.fetchone(), 'the old column is gone')
        self.cr.execute("SELECT module, name FROM ir_model_data WHERE model = 'ir.model.fields' AND res_id = %s",
                        (field_id,))
        self.assertEqual(self.cr.fetchall(), [(DASH, 'field_res_users__pk_dashboard_layout')])
        for user in (self.u1, self.u2, self.u3):
            self.assertEqual(self.normalised(user), expected[user.id])

    # ------------------------------------------------------------- UC-M1 / M2
    def test_column_move_byte_identical(self):
        before, expected, field_id = self.as_before()
        self.assertIsNone(before[self.u3.id])
        self.assertEqual(before[self.u1.id], self.texts('sc_dashboard_layout')[self.u1.id])
        moved = adopt_dashboard(self.cr)
        self.assertEqual(moved['columns'], [('res_users', 'sc_dashboard_layout', 'pk_dashboard_layout')])
        self.assert_moved(before, expected, field_id)
        # The v1 layout loads with its zones (first half left, the rest right).
        self.assertEqual([(i['id'], i['zone']) for i in expected[self.u1.id]][:2], [('gamma', 'left'), ('alpha', 'right')])
        again = adopt_dashboard(self.cr)
        self.assertEqual(again['columns'], [], 'idempotent')
        self.assert_moved(before, expected, field_id)

    # ------------------------------------------------------------- UC-M3
    def test_new_column_created_first(self):
        before, expected, field_id = self.as_before()
        self.cr.execute("ALTER TABLE res_users ADD COLUMN pk_dashboard_layout jsonb")
        self.cr.execute("CREATE TEMP TABLE pk_p7_field AS SELECT * FROM ir_model_fields WHERE id = %s", (field_id,))
        self.cr.execute("UPDATE pk_p7_field SET id = nextval('ir_model_fields_id_seq'), name = 'pk_dashboard_layout'")
        self.cr.execute("INSERT INTO ir_model_fields SELECT * FROM pk_p7_field RETURNING id")
        new_field = self.cr.fetchone()[0]
        self.cr.execute("INSERT INTO ir_model_data (module, name, model, res_id) "
                        "VALUES (%s, 'field_res_users__pk_dashboard_layout', 'ir.model.fields', %s)",
                        (DASH, new_field))
        moved = adopt_dashboard(self.cr)
        self.assertEqual(moved['columns'], [('res_users', 'sc_dashboard_layout', 'pk_dashboard_layout')])
        self.assertEqual(self.texts('pk_dashboard_layout'), before, 'byte-identical')
        self.cr.execute("SELECT count(*) FROM ir_model_fields WHERE model = 'res.users' "
                        "AND name IN ('sc_dashboard_layout', 'pk_dashboard_layout')")
        self.assertEqual(self.cr.fetchone()[0], 1)
        for user in (self.u1, self.u2, self.u3):
            self.assertEqual(self.normalised(user), expected[user.id])

    # ------------------------------------------------------------- UC-M4
    def test_install_hook(self):
        self.assertEqual(DASH_MOVED_COLUMNS[0][1:3], ('sc_dashboard_layout', 'pk_dashboard_layout'))
        self.assertEqual([new for _m, _old, new in DASH_ADOPTED_VIEWS], ['pk_dash_section', 'pk_dash_configure'])
        before, expected, field_id = self.as_before()
        hooks.pre_init_hook(self.env)
        self.assert_moved(before, expected, field_id)
        for name in ('pk_dash_section', 'pk_dash_configure'):
            self.assertTrue(self.env.ref('%s.%s' % (DASH, name)))
