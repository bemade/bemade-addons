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
    "name": "Conversation Sent Recipients",
    "version": "19.0.1.0.1",
    "category": "Discuss",
    "summary": "Show who a mail sent from a conversation went to (To and Cc).",
    "description": """
Conversation Sent Recipients
============================

When a mail is sent from a conversation, the message kept in the
conversation now lists the To and Cc addresses it actually went out to,
directly under the author line.

* The list is recorded at send time, from the headers that were put on the
  wire, and never re-derived afterwards.
* Blind-copied (Bcc) addresses still receive the mail but are never
  recorded or displayed.
* Inbound mail, internal notes and forward notes are displayed as before.
* Recording recipients sends no email and creates no partner or follower.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "conversation_email_base",
    ],
    "data": [
        "security/ir.model.access.csv",
    ],
    "assets": {
        "web.assets_backend": [
            "conversation_sent_recipients/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
