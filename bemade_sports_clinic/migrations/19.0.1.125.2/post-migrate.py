"""Task 1728 — the briefing emails' muted grey, in every language.

The morning briefing and the urgent summary are translated as a whole field
(``mail.template.body_html``). An upgrade rewrites the en_US value from the
XML but keeps the stored fr_CA one, which still carries the old #888 grey
(3.5:1 on white). Rewrite that inline colour in every language value.
"""
import logging

_logger = logging.getLogger(__name__)

OLD = 'color:#888;font-size:12px;'
NEW = 'color:#767676;font-size:12px;'
TEMPLATES = ('mail_template_morning_digest', 'mail_template_urgent_summary')


def migrate(cr, version):
    cr.execute(
        """
        UPDATE mail_template t
           SET body_html = (
                   SELECT jsonb_object_agg(key, replace(value, %(old)s, %(new)s))
                     FROM jsonb_each_text(t.body_html))
          FROM ir_model_data d
         WHERE d.model = 'mail.template'
           AND d.module = 'bemade_sports_clinic'
           AND d.name IN %(names)s
           AND d.res_id = t.id
           AND t.body_html::text LIKE %(like)s
        """,
        {'old': OLD, 'new': NEW, 'names': TEMPLATES, 'like': '%%%s%%' % OLD},
    )
    _logger.info("Task 1728: muted grey rewritten in %s briefing template(s)", cr.rowcount)
