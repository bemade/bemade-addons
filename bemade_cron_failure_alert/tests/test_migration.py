"""Use case: upgrade from 19.0.1.0.x / 19.0.1.1.0 to the additive routing.

Acceptance criteria:

1. A scheduled action in the old "Custom" mode becomes "On" (``default``): its
   single alert user moves into "Also alert", its channel is kept as the extra
   channel.
2. A "Custom" scheduled action with no user becomes "On" with no extra user.
3. Scheduled actions in "Use Settings" or "Off" are left as they are.
4. The single Settings user (old parameter) is merged into the Settings user
   list and the old parameter is removed; users already in the list are kept
   and never doubled.
5. Running the migration again changes nothing.
6. Upgrading from 19.0.1.0.x (no per-action user column yet) works too.
"""

import importlib.util
import os

from odoo.tests import tagged

from odoo.addons.bemade_cron_failure_alert.models.ir_cron import (
    PARAM_USER_LEGACY,
    PARAM_USERS,
)

from .common import CronAlertCase

SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "migrations",
    "19.0.1.2.0",
    "post-migrate.py",
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("cron_alert_post_1_2_0", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.migrate


@tagged("post_install", "-at_install")
class TestMigration(CronAlertCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.migrate = staticmethod(_load_migration())
        cls.custom_cron = cls.cron.copy({"name": cls.cron.name + " custom"})
        cls.custom_no_user = cls.cron.copy({"name": cls.cron.name + " custom bare"})
        cls.off_cron = cls.cron.copy({"name": cls.cron.name + " off"})
        cls.other_user = cls.env["res.users"].create(
            {
                "name": "Old Custom Target",
                "login": "old.custom.target@example.com",
                "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def _seed_round_two(self, with_column=True):
        """Put the DB in the 19.0.1.1.0 shape (old column + custom mode)."""
        cr = self.env.cr
        self.env.flush_all()
        if with_column:
            cr.execute(
                "ALTER TABLE ir_cron ADD COLUMN IF NOT EXISTS failure_alert_user_id int4"
            )
            cr.execute(
                "UPDATE ir_cron SET failure_alert_mode = 'custom', "
                "failure_alert_user_id = %s, failure_alert_channel_id = %s "
                "WHERE id = %s",
                [self.other_user.id, self.channel.id, self.custom_cron.id],
            )
            cr.execute(
                "UPDATE ir_cron SET failure_alert_mode = 'custom', "
                "failure_alert_user_id = NULL WHERE id = %s",
                [self.custom_no_user.id],
            )
        cr.execute(
            "UPDATE ir_cron SET failure_alert_mode = 'off' WHERE id = %s",
            [self.off_cron.id],
        )
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PARAM_USER_LEGACY, str(self.alert_user.id))
        self.env.flush_all()
        self.env.invalidate_all()

    def _run_migration(self):
        self.env.flush_all()
        self.migrate(self.env.cr, "19.0.1.1.0")
        self.env.invalidate_all()

    def test_custom_mode_becomes_also_alert(self):
        self._seed_round_two()
        self._run_migration()
        self.assertEqual(self.custom_cron.failure_alert_mode, "default")
        self.assertEqual(self.custom_cron.failure_alert_user_ids, self.other_user)
        self.assertEqual(self.custom_cron.failure_alert_channel_id, self.channel)
        self.assertEqual(self.custom_no_user.failure_alert_mode, "default")
        self.assertFalse(self.custom_no_user.failure_alert_user_ids)
        self.assertEqual(self.off_cron.failure_alert_mode, "off")
        self.assertEqual(self.cron.failure_alert_mode, "default")
        self.assertFalse(self.cron.failure_alert_user_ids)
        self.env.cr.execute("SELECT count(*) FROM ir_cron WHERE failure_alert_mode = 'custom'")
        self.assertEqual(self.env.cr.fetchone()[0], 0)

    def test_settings_user_merged_into_the_list(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PARAM_USERS, str(self.other_user.id))
        self._seed_round_two()
        self._run_migration()
        self.assertFalse(icp.get_param(PARAM_USER_LEGACY))
        self.assertEqual(
            self.env["ir.cron"]._cron_failure_alert_settings_users(),
            self.alert_user | self.other_user,
        )

    def test_settings_user_already_listed_is_not_doubled(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(PARAM_USERS, str(self.alert_user.id))
        self._seed_round_two()
        self._run_migration()
        self.assertEqual(icp.get_param(PARAM_USERS), str(self.alert_user.id))

    def test_migration_is_idempotent(self):
        self._seed_round_two()
        self._run_migration()
        icp = self.env["ir.config_parameter"].sudo()
        users_param = icp.get_param(PARAM_USERS)
        self._run_migration()
        self.assertEqual(icp.get_param(PARAM_USERS), users_param)
        self.assertEqual(self.custom_cron.failure_alert_mode, "default")
        self.assertEqual(self.custom_cron.failure_alert_user_ids, self.other_user)
        self.assertEqual(self.custom_cron.failure_alert_channel_id, self.channel)

    def test_upgrade_from_round_one(self):
        self._seed_round_two(with_column=False)
        self.env.cr.execute(
            "ALTER TABLE ir_cron DROP COLUMN IF EXISTS failure_alert_user_id"
        )
        self._run_migration()
        self.assertEqual(
            self.env["ir.cron"]._cron_failure_alert_settings_users(), self.alert_user
        )
        self.assertEqual(self.off_cron.failure_alert_mode, "off")
