#
#    Bemade Inc.
#
#    Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
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
    "name": "MRP MTS Else MTO Parent Link Fix",
    "version": "19.0.1.0.0",
    "summary": "Fix parent-child MO relationships with mts_else_mto rules",
    "description": """
MRP MTS Else MTO Parent Link Fix
================================

Fixes parent-child Manufacturing Order relationships when using
``mts_else_mto`` (Make To Stock else Make To Order) procurement rules.

Without this module, child MOs created via ``mts_else_mto`` rules are not
linked back to their parent MO, so the Parent/Child smart buttons do not
appear and quantity changes do not propagate.

This module overrides ``stock.move._prepare_procurement_values()`` to
include ``move_dest_ids`` when the rule's ``procure_method`` is
``mts_else_mto``, restoring the parent link.
""",
    "category": "Manufacturing/Manufacturing",
    "author": "Bemade Inc.",
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["mrp", "stock"],
    "data": [],
    "installable": True,
    "auto_install": False,
}
