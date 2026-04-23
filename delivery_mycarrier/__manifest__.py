#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License,
#    version 3.
#
#    For full license details, see https://www.gnu.org/licenses/lgpl-3.0.en.html.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#
{
    "name": "Delivery MyCarrier",
    "version": "19.0.2.0.0",
    "summary": "MyCarrier LTL rate estimates on sale quotations",
    "description": """
Delivery MyCarrier
==================

Integrates Odoo with the `MyCarrier <https://mycarrier.io>`_ LTL shipping
platform so that sales users can obtain LTL rate estimates at the quotation
stage without leaving Odoo.

Features
--------

* Register ``MyCarrier`` as a delivery carrier type on ``delivery.carrier``.
* Rate LTL shipments at the quotation stage via the free MyCarrier Rating API.
* Per-product NMFC freight class and NMFC code overrides that feed the rate
  payload for accurate quotes.

Scope
-----

This module covers **rate estimates only** (MyCarrier Rating API, free tier).
It does not book shipments, receive webhooks, attach BOL/label documents, or
cancel orders via the MyCarrier Orders API (paid tier). Operators book
shipments directly in the MyCarrier web application.

MyCarrier is LTL-only. This module does **not** handle parcel shipments.
""",
    "category": "Delivery",
    "author": "Bemade Inc.",
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "stock_delivery",
        "mail",
    ],
    "data": [
        "data/delivery_mycarrier_data.xml",
        "views/delivery_carrier_views.xml",
        "views/product_template_views.xml",
    ],
    "assets": {},
    "installable": True,
    "auto_install": False,
}
