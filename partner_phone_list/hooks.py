# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
import logging

from psycopg2.extras import execute_values

from odoo.tools import sql

from .tools import number_key, same_digits

_logger = logging.getLogger(__name__)

# Columns created ahead of the ORM so that existing phone numbers can be seeded
# before ``phone`` becomes computed. ``number_sanitized`` is filled here too, so
# the ORM does not recompute it (and the unique index sees final values).
_TABLE = "res_partner_phone"
_COLUMNS = [
    ("partner_id", "int4 NOT NULL", "Contact"),
    ("sequence", "int4", "Sequence"),
    ("type", "varchar NOT NULL", "Type"),
    ("number", "varchar NOT NULL", "Number"),
    ("extension", "varchar", "Extension"),
    ("label", "varchar", "Label"),
    ("number_sanitized", "varchar", "Sanitized Number"),
    ("create_uid", "int4", "Created by"),
    ("create_date", "timestamp", "Created on"),
    ("write_uid", "int4", "Last Updated by"),
    ("write_date", "timestamp", "Last Updated on"),
]


def pre_init_hook(env):
    cr = env.cr
    if not sql.table_exists(cr, _TABLE):
        sql.create_model_table(cr, _TABLE, "Contact Phone Number", _COLUMNS)
    stats = seed_phone_lines(env)
    _logger.info("partner_phone_list: seeded phone lines: %s", stats)


def seed_phone_lines(env, partner_ids=None):
    """Create one line per contact from ``res_partner.phone`` (type office) and
    from the legacy ``res_partner.mobile`` column when it exists (type mobile),
    raw values unchanged. Contacts that already have lines are skipped.

    Works in SQL (no ORM on res.partner), so it can run before the module's
    fields are set up.
    """
    cr = env.cr
    has_mobile = sql.column_exists(cr, "res_partner", "mobile")
    mobile_col = "p.mobile" if has_mobile else "NULL"
    where_ids = "AND p.id IN %(ids)s" if partner_ids else ""
    cr.execute(
        f"""
        SELECT p.id, NULLIF(TRIM(p.phone), ''), NULLIF(TRIM({mobile_col}), ''),
               c.code, c.phone_code
          FROM res_partner p
     LEFT JOIN res_country c ON c.id = p.country_id
         WHERE (COALESCE(TRIM(p.phone), '') <> ''
                OR COALESCE(TRIM({mobile_col}), '') <> '')
           AND NOT EXISTS (SELECT 1 FROM {_TABLE} l WHERE l.partner_id = p.id)
           {where_ids}
        """,
        {"ids": tuple(partner_ids or ()) or (0,)},
    )
    rows = cr.fetchall()
    default_country = env.company.country_id
    default = (default_country.code, default_country.phone_code)
    values = []
    stats = {"partners": len(rows), "office": 0, "mobile": 0, "merged": 0}
    for partner_id, phone, mobile, code, phone_code in rows:
        country = (code, phone_code) if code else default
        lines = []
        if phone:
            lines.append(["office", phone, number_key(phone, None, *country)])
        if mobile:
            key = number_key(mobile, None, *country)
            if phone and key == lines[0][2] and same_digits(phone, mobile):
                # one number in both fields: keep the phone value, typed mobile
                lines[0][0] = "mobile"
                stats["merged"] += 1
                mobile = None
            else:
                lines.append(["mobile", mobile, key])
        stats["office"] += bool(phone)
        stats["mobile"] += bool(mobile)
        for index, (ptype, number, key) in enumerate(lines):
            values.append((partner_id, (index + 1) * 10, ptype, number, key[0] if key[2] else None))
    if values:
        execute_values(
            cr._obj,
            f"""INSERT INTO {_TABLE}
                (partner_id, sequence, type, number, number_sanitized,
                 create_uid, write_uid, create_date, write_date)
                VALUES %s""",
            [v + (env.uid, env.uid) for v in values],
            template="(%s, %s, %s, %s, %s, %s, %s, now() at time zone 'UTC', now() at time zone 'UTC')",
            page_size=1000,
        )
    return stats

