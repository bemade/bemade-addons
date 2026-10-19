#
#    Bemade Inc.
#
#    Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact: marc@bemade.org)
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
    "name": "Conversation Record Tab",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Show the conversations linked to a record in its chatter.",
    "description": """
Relevant Conversations tab
==========================

Adds a "Relevant Conversations" tab to the chatter of every record whose
form uses the standard chatter. It lists the conversations that are
explicitly linked to the record (whatever created the link), newest
activity first, with their status and assignee; a click opens the
conversation.

A link is a reference, not a copy: nothing is posted on the record, and a
record without linked conversations shows no change at all. Internal users
only.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["conversation_base"],
    "assets": {
        "web.assets_backend": [
            "conversation_record_tab/static/src/chatter/**/*",
        ],
        # Tours ship in the test bundle only.
        "web.assets_tests": [
            "conversation_record_tab/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
