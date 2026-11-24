"""19.0.1.2.0: additive alert routing.

* The single Settings user (``bemade_cron_failure_alert.user_id``) joins the
  Settings user list (``bemade_cron_failure_alert.user_ids``); the old
  parameter is removed.
* A scheduled action in the removed "Custom" mode becomes "On" (``default``):
  its single alert user (old column ``failure_alert_user_id``) moves into
  "Also alert" (``failure_alert_user_ids``) and its channel stays as the extra
  channel.

Idempotent: a second run finds no old parameter and no "custom" row, and the
user link is only inserted when missing.
"""

import logging

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists

_logger = logging.getLogger(__name__)

PARAM_USERS = "bemade_cron_failure_alert.user_ids"
PARAM_USER_LEGACY = "bemade_cron_failure_alert.user_id"


def _migrate_settings_user(cr):
    cr.execute(
        "SELECT key, value FROM ir_config_parameter WHERE key IN %s",
        [(PARAM_USERS, PARAM_USER_LEGACY)],
    )
    params = dict(cr.fetchall())
    if PARAM_USER_LEGACY not in params:
        return
    ids = []
    for part in (params.get(PARAM_USERS) or "").split(","):
        part = part.strip()
        if part.isdigit() and int(part) not in ids:
            ids.append(int(part))
    legacy = (params[PARAM_USER_LEGACY] or "").strip()
    if legacy.isdigit() and int(legacy) not in ids:
        ids.append(int(legacy))
    value = ",".join(str(i) for i in ids)
    if PARAM_USERS in params:
        cr.execute(
            "UPDATE ir_config_parameter SET value = %s WHERE key = %s",
            [value, PARAM_USERS],
        )
    elif value:
        cr.execute(
            "INSERT INTO ir_config_parameter (key, value, create_uid, create_date, "
            "write_uid, write_date) VALUES (%s, %s, 1, now() at time zone 'UTC', "
            "1, now() at time zone 'UTC')",
            [PARAM_USERS, value],
        )
    cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", [PARAM_USER_LEGACY])
    _logger.info("Scheduled action failure alerts: Settings users are now %s", value)


def _migrate_custom_crons(cr):
    if column_exists(cr, "ir_cron", "failure_alert_user_id"):
        cr.execute(
            """
            INSERT INTO ir_cron_failure_alert_user_rel (cron_id, user_id)
            SELECT c.id, c.failure_alert_user_id
              FROM ir_cron c
              JOIN res_users u ON u.id = c.failure_alert_user_id
             WHERE c.failure_alert_mode = 'custom'
            ON CONFLICT DO NOTHING
            """
        )
    cr.execute(
        "UPDATE ir_cron SET failure_alert_mode = 'default' "
        "WHERE failure_alert_mode = 'custom' RETURNING id"
    )
    ids = [row[0] for row in cr.fetchall()]
    if ids:
        _logger.info(
            "Scheduled action failure alerts: %s scheduled action(s) moved from "
            "Custom to On with their user in Also alert: %s",
            len(ids),
            ids,
        )


def migrate(cr, version):
    if not version:
        return
    _migrate_settings_user(cr)
    _migrate_custom_crons(cr)
    # parameters are read through an ormcache: drop what SQL just changed
    api.Environment(cr, SUPERUSER_ID, {}).registry.clear_cache("stable")
