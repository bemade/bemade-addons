"""Back-fill the French translation of imported content.

Content was imported before the module captured both languages, so the French
text sits in the source-language slot with no translation beside it: an English
reader sees French believing it is English, and a French reader only gets it
through fallback rather than from a real fr_CA value.

Copy the source value into every active French locale that does not already
carry something of its own. Reading a locale with no translation returns the
source value, so "reads the same as the source" is exactly the set to fill, and
writing the same string back is harmless — which makes this idempotent. The
visible text does not change in either language; the French merely becomes
explicit, so a later import can replace the source value with the English fiche
without disturbing it.
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

# (model, candidate content fields) — the customer's plan, not module chrome.
CONTENT = [
    ("cbet.domain", ["name"]),
    ("cbet.competency", ["name", "execution_context", "safety_block",
                         "tools_materials", "common_pitfalls",
                         "protocol_method", "protocol_place", "protocol_support"]),
    ("cbet.evaluation.unit", ["name", "protocol_notes"]),
    ("cbet.criterion", ["text", "verification_method", "tolerance"]),
    ("cbet.question", ["text", "expected_answer"]),
    ("cbet.standard", ["name", "role_description"]),
]


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    french = env["res.lang"].search([("code", "=like", "fr%")]).mapped("code")
    if not french:
        _logger.info("hr_skills_cbet: no French locale active, nothing to back-fill")
        return

    for model_name, candidates in CONTENT:
        model = env[model_name]
        fields_to_do = [f for f in candidates
                        if f in model._fields and model._fields[f].translate]
        if not fields_to_do:
            continue
        filled = 0
        for record in model.with_context(active_test=False).search([]):
            for field in fields_to_do:
                source = record.with_context(lang="en_US")[field]
                if not source:
                    continue
                untranslated = [lang for lang in french
                                if record.with_context(lang=lang)[field] == source]
                if not untranslated:
                    continue
                if callable(model._fields[field].translate):
                    # Html/Xml fields translate term by term, so the whole value
                    # has to go through a write rather than a translation dict.
                    for lang in untranslated:
                        record.with_context(lang=lang).write({field: source})
                else:
                    record.update_field_translations(
                        field, {lang: source for lang in untranslated})
                filled += 1
        _logger.info("hr_skills_cbet: back-filled French on %s %s value(s)",
                     filled, model_name)
