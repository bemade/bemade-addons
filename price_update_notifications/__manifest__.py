#
#    Bemade Inc.
#
#    Copyright (C) 2023-June Bemade Inc. (<https://www.bemade.org>).
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
    "name": "Price Update Notifications",
    "version": "17.0.1.0.0",
    "summary": "Send a price update notification to clients",
    "category": "Sale",
    "author": "Bemade Inc.",
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["sale_management", "sales_team", "mail"],
    "data": [
        "security/ir.model.access.csv",
        "data/ir_cron_data.xml",
        "data/email_templates.xml",
        "views/price_notice_mailing_views.xml",
        "wizard/send_price_update_notice_views.xml",
    ],
    "assets": {},
    "installable": True,
    "auto_install": False,
}
