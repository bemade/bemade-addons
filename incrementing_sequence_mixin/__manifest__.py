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
    "name": "Incrementing Sequence Mixin",
    "version": "19.0.1.0.0",
    "summary": "Adds an incrementing.sequence.mixin model to inherit from.",
    "description": """
    Adds an incrementing.sequence.mixin model to inherit from. This model adds a
    sequence field to the models that inherit from it, including the logic to set it to
    the highest current sequence number + 1 by default and to leave it otherwise
    changeable by the user (i.e. with a drag and drop via the handle).
    
    Specify the _sequence_group attribute on the model to indicate which field to use
    to determine if records belong to the same group. For example, if one were to use
    this on sale.order.line, they could specify "order_id" as the _sequence_group such
    that newly created lines take on the highest sequence number of all lines on the
    same sales order.
    """,
    "category": "",
    "author": "Bemade Inc.",
    "website": "http://www.bemade.org",
    "license": "LGPL-3",
    "depends": [],
    "data": [],
    "assets": {},
    "installable": True,
    "auto_install": False,
}
