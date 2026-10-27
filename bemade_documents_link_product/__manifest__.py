{
    "name": "Documents - Link Existing (Products)",
    "version": "19.0.1.0.0",
    "summary": "Show documents linked to a product in its Documents button.",
    "category": "Productivity/Documents",
    "author": "Bemade Inc.",
    "maintainer": "Marc Durepos <marc@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["bemade_documents_link", "product"],
    "data": ["views/product_document_views.xml"],
    "assets": {
        "web.assets_tests": [
            "bemade_documents_link_product/static/tests/tours/*.js",
        ],
    },
    "installable": True,
    "auto_install": True,
    "post_init_hook": "post_init_hook",
}
