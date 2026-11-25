# -*- coding: utf-8 -*-
"""19.0.8.4.2 — correction lines name the field in the student's language. Before this
version the label was the writer's language, so a parent using Odoo in English wrote
« (What worked) » into a French student's journal. This script rewrites, in the
``corrections`` of journal entries and blocks, the label right after the dated prefix
(``- **YYYY-MM-DD** (<label>):``) from the frozen field's source (English) string to its
label in the student's language. The text after the label is never touched; lines already
translated and students without a language (or in English) are left alone. Idempotent.
"""
import logging
import re

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

MODELS = ("homeschool.journal", "homeschool.block")
PREFIX = r"^(- \*\*\d{4}-\d{2}-\d{2}\*\* )\((%s)\):"


def rewrite_correction_labels(env):
    """Rewrite the English labels of existing correction lines; returns the number of
    records changed."""
    changed = 0
    for model_name in MODELS:
        Model = env[model_name].with_context(active_test=False, tracking_disable=True)
        records = Model.search([("corrections", "!=", False)])
        for lang, recs in records.grouped(lambda r: r.student_id.partner_id.lang or "").items():
            if not lang:
                continue
            lang_env = Model.with_context(lang=lang).env
            mapping = {}
            for field_name in Model._frozen_fields:
                field = Model._fields[field_name]
                label = field._description_string(lang_env)
                if label and label != field.string:
                    mapping[field.string] = label
            if not mapping:
                continue
            pattern = re.compile(PREFIX % "|".join(re.escape(k) for k in mapping), re.M)
            for rec in recs:
                new = pattern.sub(lambda m: "%s(%s):" % (m.group(1), mapping[m.group(2)]), rec.corrections)
                if new != rec.corrections:
                    # ``corrections`` is not a frozen field: a plain write
                    rec.write({"corrections": new})
                    changed += 1
        _logger.info("homeschool: correction labels rewritten on %s", model_name)
    _logger.info("homeschool: %d records with correction labels rewritten", changed)
    return changed


def migrate(cr, version):
    rewrite_correction_labels(api.Environment(cr, SUPERUSER_ID, {}))
