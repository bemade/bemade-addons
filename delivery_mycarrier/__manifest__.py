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
    "version": "19.0.1.0.0",
    "summary": "MyCarrier LTL shipping integration",
    "description": """
Delivery MyCarrier
==================

Integrates Odoo with the `MyCarrier <https://mycarrier.io>`_ LTL shipping
platform so that sales, warehouse and logistics users can rate, book and
track LTL shipments without leaving Odoo.

Features
--------

* Register ``MyCarrier`` as a delivery carrier type on ``delivery.carrier``.
* Rate LTL shipments at the quotation stage via the MyCarrier Rating API.
* Book shipments automatically when an outgoing picking is validated via
  the MyCarrier Orders API.
* Receive shipment status, tracking updates, cancellations and final
  pricing via inbound webhooks (``shipment.created``,
  ``shipment.tracking.updated``, ``shipment.canceled``).
* Attach the MyCarrier-generated BOL and shipping label PDFs to the
  related ``stock.picking`` when the shipment is confirmed.
* Per-product NMFC freight class and NMFC code overrides.
* Separate sandbox and production environments.

Scope
-----

MyCarrier is LTL-only. This module does **not** handle parcel shipments.
Cancellation is exposed as a guided ``UserError`` pointing operators to
the MyCarrier web UI until a cancellation endpoint is confirmed with
MyCarrier support.
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
        "views/stock_picking_views.xml",
        "views/product_template_views.xml",
    ],
    "assets": {},
    "installable": True,
    "auto_install": False,
}
