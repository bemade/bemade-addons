"""Task 1739 (19.0.1.133.0) — every clinic activity is a To-Do, « À faire ».

``mail.mail_activity_data_todo`` is a ``noupdate`` record of ``mail`` (shipped
« To-Do », untranslated in French), so only a script reaches existing
databases:

1. the To-Do type reads « À faire » in fr_CA (and fr_FR when installed) —
   name and default summary, when still the English « To-Do »;
2. the activities on the clinic's models (``sports.*``) whose type is not
   To-Do (Email, Call, … or none) become To-Do. Other modules' activities are
   not touched.

Idempotent: a second run finds nothing to convert and nothing to rename.
"""
import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = env["mail.activity.type"]._sc_set_todo_french_name()
    _logger.info("#1739: To-Do type « À faire » ensured in %s", ", ".join(langs) or "no French language")
    counts = env["mail.activity"]._sc_convert_clinic_activities_to_todo()
    if not counts:
        _logger.info("#1739: no clinic activity to convert to To-Do")
    for model, count in sorted(counts.items()):
        _logger.info("#1739: %s: %s activities converted to To-Do", model, count)
    _logger.info("#1739: %s clinic activities converted to To-Do in all", sum(counts.values()))
