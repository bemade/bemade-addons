from . import models
from . import wizard


def post_init_hook(env):
    """À l'installation sur une base existante : reflète chaque lien natif
    (res_model/res_id déjà posés sur les documents) en ligne
    bemade.documents.link, comme la migration 2.0.0 le fait à l'upgrade."""
    documents = env["documents.document"].search(
        [("res_model", "!=", False), ("res_id", "!=", False),
         ("res_model", "!=", "documents.document")]
    )
    if not documents:
        return
    Link = env["bemade.documents.link"]
    existing = Link.search([("document_id", "in", documents.ids)])
    seen = {(l.document_id.id, l.res_model, l.res_id) for l in existing}
    vals = [
        {"document_id": d.id, "res_model": d.res_model, "res_id": d.res_id}
        for d in documents
        if (d.id, d.res_model, d.res_id) not in seen
    ]
    if vals:
        Link.with_context(skip_bemade_link_audit=True).create(vals)
