# -*- coding: utf-8 -*-
"""19.0.5.0.0 — files linked to a trace or a material before this version may still
carry ``res_id = 0`` (uploaded in the backend before the record was saved): they were
invisible to portal users. From this version the models stamp such files on link; this
script stamps the ones already there, through the relation tables and the material's
``pdf_attachment_id``. Idempotent: only attachments without a record are touched.
"""
import logging

_logger = logging.getLogger(__name__)

ORPHAN = "(a.res_id IS NULL OR a.res_id = 0 OR a.res_model IS NULL OR a.res_model = '')"

STAMPS = [
    ("homeschool.trace",
     "UPDATE ir_attachment a SET res_model = 'homeschool.trace', res_id = r.trace_id "
     "FROM homeschool_trace_attachment_rel r WHERE r.attachment_id = a.id AND " + ORPHAN),
    ("homeschool.material",
     "UPDATE ir_attachment a SET res_model = 'homeschool.material', res_id = r.material_id "
     "FROM homeschool_material_attachment_rel r WHERE r.attachment_id = a.id AND " + ORPHAN),
    ("homeschool.material (pdf)",
     "UPDATE ir_attachment a SET res_model = 'homeschool.material', res_id = m.id "
     "FROM homeschool_material m WHERE m.pdf_attachment_id = a.id AND " + ORPHAN),
]


def stamp_orphan_attachments(cr):
    """Run the stamping queries; returns the number of attachments stamped."""
    total = 0
    for label, query in STAMPS:
        cr.execute(query)
        _logger.info("homeschool: %d orphan attachments stamped for %s", cr.rowcount, label)
        total += cr.rowcount
    return total


def migrate(cr, version):
    stamp_orphan_attachments(cr)
