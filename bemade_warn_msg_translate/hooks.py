# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
import logging

from psycopg2.extras import Json

from odoo.tools import SQL

from .tools.split import analyse_bilingual

_logger = logging.getLogger(__name__)

WARNING_FIELDS = [
    ("res.partner", "sale_warn_msg"),
    ("res.partner", "purchase_warn_msg"),
    ("res.partner", "picking_warn_msg"),
    ("product.template", "sale_line_warn_msg"),
    ("product.template", "purchase_line_warn_msg"),
]

UNTOUCHED = ("empty", "single", "monolingual")


def _rows(env, model, fname):
    table = env[model]._table
    env.cr.execute(SQL(
        "SELECT id, %s FROM %s WHERE %s IS NOT NULL ORDER BY id",
        SQL.identifier(fname), SQL.identifier(table), SQL.identifier(fname),
    ))
    return table, env.cr.fetchall()


def _write(env, table, fname, rec_id, value):
    env.cr.execute(SQL(
        "UPDATE %s SET %s = %s WHERE id = %s",
        SQL.identifier(table), SQL.identifier(fname), Json(value), rec_id,
    ))


def split_existing_warnings(env):
    """Split the bilingual « French ⏎⏎ English » warnings into translations.

    Only values that are not translated yet (a single distinct text across
    all their languages, as the text→jsonb conversion leaves them) are
    considered. The French part goes to every active French language, the
    English part to ``en_US``. Returns ``{"model.field": {"split": n,
    "untouched": n, "ambiguous": n, "reversed": n}}``; ``reversed`` is the
    part of ``ambiguous`` written English first.
    """
    env.flush_all()
    fr_langs = [code for code, _name in env["res.lang"].get_installed() if code.startswith("fr")]
    if not fr_langs:
        _logger.info("No French language active: warning messages left as they are.")
        return {}
    stats = {}
    for model, fname in WARNING_FIELDS:
        counts = stats[f"{model}.{fname}"] = dict.fromkeys(
            ("split", "untouched", "ambiguous", "reversed"), 0
        )
        ambiguous_ids = []
        table, rows = _rows(env, model, fname)
        for rec_id, value in rows:
            if not value or len(set(value.values())) != 1:
                continue  # already translated by someone
            status, french, english = analyse_bilingual(next(iter(value.values())))
            if status == "empty":
                continue
            if status in UNTOUCHED:
                counts["untouched"] += 1
                continue
            if status != "split":
                counts["ambiguous"] += 1
                counts["reversed"] += status == "reversed"
                ambiguous_ids.append(rec_id)
                continue
            new_value = dict(value, en_US=english)
            new_value.update(dict.fromkeys(fr_langs, french))
            _write(env, table, fname, rec_id, new_value)
            counts["split"] += 1
        _logger.info(
            "%s.%s: %d split into French/English, %d left as they are, "
            "%d not split because unclear (of which %d English first)%s",
            model, fname, counts["split"], counts["untouched"], counts["ambiguous"],
            counts["reversed"], f": ids {ambiguous_ids}" if ambiguous_ids else "",
        )
    env.invalidate_all()
    return stats


def merge_translations_back(env):
    """Fold translations into one bilingual ``en_US`` text before uninstall.

    When the fields stop being translatable, the ORM keeps only the
    ``en_US`` value. Every other distinct value is put in front of it
    (French first), separated by a blank line, so nothing is lost.
    """
    env.flush_all()
    for model, fname in WARNING_FIELDS:
        table, rows = _rows(env, model, fname)
        merged_count = 0
        for rec_id, value in rows:
            if not value or len(set(value.values())) == 1:
                continue
            english = value.get("en_US")
            others = []
            for lang in sorted(value, key=lambda code: (not code.startswith("fr"), code)):
                text = value[lang]
                if lang != "en_US" and text and text != english and text not in others:
                    others.append(text)
            merged = "\n\n".join(others + ([english] if english else []))
            _write(env, table, fname, rec_id, {"en_US": merged})
            merged_count += 1
        _logger.info("%s.%s: %d translated warnings folded back into one text", model, fname, merged_count)
    env.invalidate_all()


def post_init_hook(env):
    split_existing_warnings(env)


def uninstall_hook(env):
    merge_translations_back(env)
