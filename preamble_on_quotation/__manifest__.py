#    Bemade Inc.
#
#    Copyright (C) 2025-April Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : mdurepos@durpro.com)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Quotation PDF Preamble",
    "version": "19.0.0.2.0",
    "license": "LGPL-3",
    "category": "Sales",
    "summary": "Add customizable HTML preamble to quotation PDFs and the customer portal",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["base", "sale"],
    "data": [
        "views/sale_order_views.xml",
        "report/sale_report_templates.xml",
        "views/res_company_views.xml",
        "views/sale_portal_templates.xml",
    ],
    "description": """
    Quotation PDF Preamble
    ======================

    This module enhances the standard quotation PDF reports by allowing users to add a
    customizable HTML preamble at the beginning of the document. The preamble appears
    before the quotation details, similar to how the terms and conditions appear after.

    The same preamble is shown to the customer on the online quotation (portal) view,
    so the web and PDF versions of a quotation tell the same story.

    Features:
    ---------
    * Add a configurable HTML preamble field to sales orders
    * Display the preamble at the top of quotation PDF reports
    * Display the preamble above the order details on the customer portal
    * Company-specific default preambles that can be overridden per quotation
    * Uses Odoo's standard HTML field type for content editing

    This module is ideal for businesses that need to include standard disclaimers,
    terms and conditions, or promotional content at the beginning of their quotations.
    """,
    "installable": True,
    "application": False,
    "auto_install": False,
}
