import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

GLUE_MODULES = (
    # (glue module, module it bridges to)
    ("bemade_documents_link_product", "product"),
    ("bemade_documents_link_hr", "documents_hr"),
)


def _mirror_native_primaries(env):
    """Documents that have link rows but whose native primary has no row get
    that row, so every record a document is attached to is represented."""
    Link = env["bemade.documents.link"]
    documents = env["documents.document"].search(
        [
            ("bemade_link_ids", "!=", False),
            ("res_model", "!=", False),
            ("res_id", "!=", False),
            ("res_model", "!=", "documents.document"),
        ]
    )
    rows = Link.search([("document_id", "in", documents.ids)])
    seen = {(r.document_id.id, r.res_model, r.res_id) for r in rows}
    vals_list = [
        {"document_id": d.id, "res_model": d.res_model, "res_id": d.res_id}
        for d in documents
        if (d.id, d.res_model, d.res_id) not in seen
    ]
    if vals_list:
        Link.with_context(skip_bemade_link_audit=True).create(vals_list)
    _logger.info("Mirrored %d native document primary link(s).", len(vals_list))


def _install_glue_modules(env):
    """``auto_install`` does not fire on ``-u``: queue the glue modules whose
    dependencies are installed. A glue module that is not in the addons path
    is simply not found, which makes this a no-op."""
    Module = env["ir.module.module"]
    for glue, dependency in GLUE_MODULES:
        if not Module.search_count(
            [("name", "=", dependency), ("state", "=", "installed")]
        ):
            continue
        module = Module.search([("name", "=", glue), ("state", "=", "uninstalled")])
        if module:
            module.button_install()
            _logger.info("Queued glue module %s for installation.", glue)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    _mirror_native_primaries(env)
    _install_glue_modules(env)
