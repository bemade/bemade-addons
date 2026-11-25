# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Stored data that moves from a consumer to the kit (task 5200, kit P5).

``tools/adopt.py`` moves VIEWS (same records, new external ids). This module
moves the other stored names of P5, with their data:

* user columns (``MOVED_COLUMNS``): a ``res.users`` column is renamed in
  place, so every user keeps their value; its ``ir_model_fields`` row, its
  selection rows and their external ids take the new name and the kit's
  module;
* system parameters (``MOVED_PARAMS``): each old key's value is copied to
  the new key (an absent old key stays absent: an absent parameter keeps its
  meaning), then the old key is deleted (a settings field saved « off »
  deletes its parameter; a leftover old key would turn it back on through
  the one-release fallback, ``portal.kit._pk_shell_enabled``);
* models (``MOVED_MODELS``): the model's table, its ``ir_model`` row, its
  fields, constraints, access rights and external ids are renamed in place:
  the same rows, the same ids.

Same three entry points as ``adopt_views``, for the same reasons: the kit's
install hook (a database that has the consumer but not the kit yet), the
kit's pre-migration (the kit upgraded) and the consumer's pre-migration
(the consumer upgraded alone: Odoo then re-initialises ``res.users`` from
the code, which already declares the kit's fields, and would create the new
columns empty BEFORE the kit's migration copied the old values). Each runs
BEFORE the models are initialised (plain SQL), and each helper is
idempotent: whichever entry point runs first does the work, the others find
nothing to do. When the old AND the new name both exist (the new one created
empty), the values are copied over and the old one is dropped.
"""
import logging

from psycopg2 import sql

_logger = logging.getLogger(__name__)

KIT = 'bemade_portal_kit'
CLINIC = 'bemade_sports_clinic'

# (table, old column, new column, model, old module) — task 5200.
MOVED_COLUMNS = (
    ('res_users', 'sc_theme', 'pk_theme', 'res.users', CLINIC),
    ('res_users', 'sc_show_done_buttons', 'pk_show_done_buttons', 'res.users', CLINIC),
)

# (old key, new key) — task 5200.
MOVED_PARAMS = (
    ('%s.app_shell_enabled' % CLINIC, '%s.enabled' % KIT),
    ('%s.sc_theme_choice_enabled' % CLINIC, '%s.theme_choice_enabled' % KIT),
    ('%s.help_home_url' % CLINIC, '%s.help_home_url' % KIT),
)

# (old model, new model, old module, ((old constraint, new constraint), …),
#  ((old access xmlid, new access xmlid), …)) — task 5200. A listed access right
# becomes the kit's (the kit's data declares it), the others stay the
# consumer's (they point at the renamed model).
MOVED_MODELS = (
    ('sc.help.article', 'portal.kit.help', CLINIC,
     (('key_unique', 'key_unique'),),
     (('access_sc_help_article_system', 'access_portal_kit_help_system'),)),
)


def _table(model):
    return model.replace('.', '_')


def _table_exists(cr, table):
    cr.execute("SELECT 1 FROM pg_class WHERE relname = %s AND relkind = 'r'", (table,))
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def _drop_field_rows(cr, model, name):
    """Delete the ``ir_model_fields`` row of ``model.name`` (and its
    selection rows and the external ids of both)."""
    cr.execute("SELECT id FROM ir_model_fields WHERE model = %s AND name = %s", (model, name))
    row = cr.fetchone()
    if not row:
        return
    cr.execute("SELECT id FROM ir_model_fields_selection WHERE field_id = %s", (row[0],))
    selection_ids = [r[0] for r in cr.fetchall()]
    if selection_ids:
        cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.model.fields.selection' AND res_id = ANY(%s)",
                    (selection_ids,))
        cr.execute("DELETE FROM ir_model_fields_selection WHERE id = ANY(%s)", (selection_ids,))
    cr.execute("DELETE FROM ir_model_data WHERE model = 'ir.model.fields' AND res_id = %s", (row[0],))
    cr.execute("DELETE FROM ir_model_fields WHERE id = %s", (row[0],))


def move_columns(cr, mapping=MOVED_COLUMNS, target=KIT):
    """Rename each old column (and its field metadata) to its new name; the
    field's external ids go to module ``target`` (the kit by default; task
    5202: a kit addon such as ``bemade_portal_kit_dashboard`` moves its own
    columns with the same helper). Returns the ``(table, old, new)`` moved
    or merged by this call."""
    moved = []
    for table, old, new, model, old_module in mapping:
        if not _column_exists(cr, table, old):
            continue
        if _column_exists(cr, table, new):
            # The new column was created (empty, or with its default) before
            # this ran: the old values win, then the old column goes.
            cr.execute(sql.SQL("UPDATE {t} SET {n} = {o} WHERE {o} IS NOT NULL").format(
                t=sql.Identifier(table), n=sql.Identifier(new), o=sql.Identifier(old)))
            cr.execute(sql.SQL("ALTER TABLE {t} DROP COLUMN {o}").format(
                t=sql.Identifier(table), o=sql.Identifier(old)))
            _drop_field_rows(cr, model, old)
            moved.append((table, old, new))
            _logger.info("portal kit: %s.%s merged into %s.%s", table, old, table, new)
            continue
        cr.execute(sql.SQL("ALTER TABLE {t} RENAME COLUMN {o} TO {n}").format(
            t=sql.Identifier(table), o=sql.Identifier(old), n=sql.Identifier(new)))
        _drop_field_rows(cr, model, new)  # a stale row of the new name, if any
        cr.execute(
            "UPDATE ir_model_fields SET name = %s WHERE model = %s AND name = %s RETURNING id",
            (new, model, old),
        )
        row = cr.fetchone()
        if row:
            prefix = 'field_%s__' % _table(model)
            cr.execute(
                """UPDATE ir_model_data SET module = %s, name = %s
                    WHERE model = 'ir.model.fields' AND res_id = %s AND module = %s AND name = %s""",
                (target, prefix + new, row[0], old_module, prefix + old),
            )
            # The selection values' external ids: selection__<table>__<field>__<value>.
            old_sel = 'selection__%s__%s__' % (_table(model), old)
            new_sel = 'selection__%s__%s__' % (_table(model), new)
            cr.execute(
                """UPDATE ir_model_data d SET module = %s, name = %s || substr(d.name, %s)
                     FROM ir_model_fields_selection s
                    WHERE d.model = 'ir.model.fields.selection' AND d.res_id = s.id
                      AND s.field_id = %s AND d.module = %s AND d.name LIKE %s""",
                (target, new_sel, len(old_sel) + 1, row[0], old_module, old_sel.replace('_', r'\_') + '%'),
            )
        moved.append((table, old, new))
        _logger.info("portal kit: column %s.%s renamed %s", table, old, new)
    return moved


def move_params(cr, mapping=MOVED_PARAMS):
    """Copy each old system parameter to its new key (the new key, if set,
    wins), then delete the old one. Returns the old keys moved."""
    moved = []
    for old, new in mapping:
        cr.execute("SELECT value FROM ir_config_parameter WHERE key = %s", (old,))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute("SELECT 1 FROM ir_config_parameter WHERE key = %s", (new,))
        if not cr.fetchone():
            cr.execute(
                """INSERT INTO ir_config_parameter (key, value, create_uid, write_uid, create_date, write_date)
                   SELECT %s, value, create_uid, write_uid, create_date, now() at time zone 'UTC'
                     FROM ir_config_parameter WHERE key = %s""",
                (new, old),
            )
        cr.execute("DELETE FROM ir_config_parameter WHERE key = %s", (old,))
        moved.append(old)
        _logger.info("portal kit: parameter %s moved to %s", old, new)
    return moved


def move_models(cr, mapping=MOVED_MODELS):
    """Rename each old model in place (table, metadata, external ids).
    Returns the old models moved or merged by this call."""
    moved = []
    for old, new, old_module, constraints, accesses in mapping:
        old_table, new_table = _table(old), _table(new)
        if not _table_exists(cr, old_table):
            continue
        if _table_exists(cr, new_table):
            # The new model was created first (empty): copy the rows the new
            # table lacks (same keys), the consumer's upgrade drops the old
            # model (its ir.model row still belongs to the consumer).
            cr.execute(sql.SQL(
                """INSERT INTO {n} (key, url, sequence, active, note, create_uid, create_date, write_uid, write_date)
                   SELECT o.key, o.url, o.sequence, o.active, o.note, o.create_uid, o.create_date,
                          o.write_uid, o.write_date
                     FROM {o} o WHERE NOT EXISTS (SELECT 1 FROM {n} x WHERE x.key = o.key)""").format(
                n=sql.Identifier(new_table), o=sql.Identifier(old_table)))
            moved.append(old)
            _logger.info("portal kit: %s rows copied into %s", old, new)
            continue
        cr.execute(sql.SQL("ALTER TABLE {o} RENAME TO {n}").format(
            o=sql.Identifier(old_table), n=sql.Identifier(new_table)))
        cr.execute("SELECT 1 FROM pg_class WHERE relname = %s AND relkind = 'S'", ('%s_id_seq' % old_table,))
        if cr.fetchone():
            cr.execute(sql.SQL("ALTER SEQUENCE {o} RENAME TO {n}").format(
                o=sql.Identifier('%s_id_seq' % old_table), n=sql.Identifier('%s_id_seq' % new_table)))
        cr.execute(sql.SQL("ALTER INDEX IF EXISTS {o} RENAME TO {n}").format(
            o=sql.Identifier('%s_pkey' % old_table), n=sql.Identifier('%s_pkey' % new_table)))
        for old_name, new_name in constraints:
            old_con, new_con = '%s_%s' % (old_table, old_name), '%s_%s' % (new_table, new_name)
            cr.execute("SELECT 1 FROM pg_constraint WHERE conname = %s", (old_con,))
            if cr.fetchone():
                cr.execute(sql.SQL("ALTER TABLE {t} RENAME CONSTRAINT {o} TO {n}").format(
                    t=sql.Identifier(new_table), o=sql.Identifier(old_con), n=sql.Identifier(new_con)))
            cr.execute("UPDATE ir_model_constraint SET name = %s WHERE name = %s RETURNING id", (new_con, old_con))
            for (cid,) in cr.fetchall():
                cr.execute("UPDATE ir_model_data SET module = %s, name = %s "
                           "WHERE model = 'ir.model.constraint' AND res_id = %s",
                           (KIT, 'constraint_%s' % new_con, cid))
        cr.execute("UPDATE ir_model SET model = %s WHERE model = %s RETURNING id", (new, old))
        model_row = cr.fetchone()
        cr.execute("UPDATE ir_model_fields SET model = %s WHERE model = %s", (new, old))
        cr.execute("UPDATE ir_model_fields SET relation = %s WHERE relation = %s", (new, old))
        cr.execute("UPDATE ir_model_constraint SET module = (SELECT id FROM ir_module_module WHERE name = %s) "
                   "WHERE model = %s", (KIT, model_row[0]) if model_row else (KIT, 0))
        cr.execute("UPDATE ir_model_data SET model = %s WHERE model = %s", (new, old))
        if model_row:
            cr.execute(
                "UPDATE ir_model_data SET module = %s, name = %s "
                "WHERE model = 'ir.model' AND res_id = %s AND module = %s",
                (KIT, 'model_%s' % new_table, model_row[0], old_module),
            )
            old_prefix, new_prefix = 'field_%s__' % old_table, 'field_%s__' % new_table
            cr.execute(
                """UPDATE ir_model_data d SET module = %s, name = %s || substr(d.name, %s)
                     FROM ir_model_fields f
                    WHERE d.model = 'ir.model.fields' AND d.res_id = f.id AND f.model = %s
                      AND d.module = %s AND d.name LIKE %s""",
                (KIT, new_prefix, len(old_prefix) + 1, new, old_module,
                 old_prefix.replace('_', r'\_') + '%'),
            )
        for old_xmlid, new_xmlid in accesses:
            cr.execute(
                "UPDATE ir_model_data SET module = %s, name = %s "
                "WHERE model = 'ir.model.access' AND module = %s AND name = %s",
                (KIT, new_xmlid, old_module, old_xmlid),
            )
        # Every other row naming the model by name (actions, views, …): the
        # consumer's upgrade removes its own, without errors on the way.
        for table, column in (('ir_act_window', 'res_model'), ('ir_ui_view', 'model'),
                              ('ir_attachment', 'res_model'), ('ir_default', None)):
            if column and _column_exists(cr, table, column):
                cr.execute(sql.SQL("UPDATE {t} SET {c} = %s WHERE {c} = %s").format(
                    t=sql.Identifier(table), c=sql.Identifier(column)), (new, old))
        moved.append(old)
        _logger.info("portal kit: model %s renamed %s", old, new)
    return moved


def move_data(cr):
    """Every P5 data move (columns, parameters, models), idempotent."""
    return {
        'columns': move_columns(cr),
        'params': move_params(cr),
        'models': move_models(cr),
    }
