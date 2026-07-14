{
    "name": "Web M2X Narrow-Window Inline Search",
    "version": "19.0.1.0.0",
    "category": "Technical",
    "license": "LGPL-3",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "summary": "Keep the inline autocomplete on narrow desktop windows; "
    "open the relational search dialog list-first on small screens.",
    "description": """
Web M2X Narrow-Window Inline Search
===================================

Two surgical, assets-only patches to the web client's small-screen behaviour for
relational (many2one / many2many) fields:

1. **Inline autocomplete survives a narrow desktop window.** Stock Odoo swaps the
   inline ``AutoComplete`` dropdown for a read-only input that opens a full search
   dialog whenever ``env.isSmall`` is true — but ``env.isSmall`` is purely a
   viewport-width test, so merely narrowing a desktop browser window (or a split
   pane) loses the fast inline search. This module gates that swap on
   ``env.isSmall && hasTouch()`` (the same discriminator core already uses for the
   selection field's bottom sheet), so only true touch devices get the dialog
   input; a narrow non-touch window keeps the normal inline autocomplete.

2. **Search dialog opens list-first on small screens.** When the search dialog
   *does* appear on a small screen, stock Odoo opens it in kanban view. This module
   opens it in list view instead, which is denser and easier to scan.

The module contains no models and no data — only a JS patch and an OWL template
extension (xpath, not a fork). Uninstalling it fully restores stock behaviour.
It depends on ``web`` only and carries no client-specific coupling, so it is
reusable at any client.
    """,
    "depends": ["web"],
    "assets": {
        "web.assets_backend": [
            "web_m2x_narrow_inline_search/static/src/js/many2x_narrow_inline_search.js",
            "web_m2x_narrow_inline_search/static/src/xml/many2x_narrow_inline_search.xml",
        ],
        "web.assets_unit_tests": [
            "web_m2x_narrow_inline_search/static/tests/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
    "application": False,
}
