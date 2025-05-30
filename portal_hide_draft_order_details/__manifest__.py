#
#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
#    Author: Benoît Vézina (Contact : benoit@bemade.org)
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
    "name": "Portal Order Line Hiding with Company Settings",
    "version": "17.0.1.0.0",
    "summary": "Hide order lines on the portal based on a company setting when the Sales Order is in draft state.",
    "author": "Bemade Inc.",
    "depends": ["website_sale"],
    "data": [
        "views/sale_order_portal_templates.xml",
        "wizard/res_config_settings.xml",
    ],
    "installable": True,
    "application": False,
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
}
