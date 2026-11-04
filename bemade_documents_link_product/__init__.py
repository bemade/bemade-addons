from . import models


def post_init_hook(env):
    """Backfill the ``product.document`` of every document already linked to
    a product (links made before this module was installed)."""
    links = env["bemade.documents.link"].search(
        [("res_model", "in", ("product.template", "product.product"))]
    )
    links.document_id._bemade_ensure_product_document()
