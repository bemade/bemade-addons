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
    "name": "Conversation Team Inbox",
    "version": "19.0.1.0.0",
    "category": "Discuss",
    "summary": "Shared team inbox: a per-team email alias that creates team "
    "conversations, answered from the team address.",
    "description": """
Team inbox for Conversations
============================

Each conversation team owns a mail alias and a *from address*. Mail sent to the
alias creates a conversation owned by the team (sender as requester, To/Cc as
participants, no followers) and every internal team member sees it unread.

Replying from such a conversation sends through a built-in "team mailbox"
transport that uses the team's from address and Odoo's standard outgoing mail
server lookup (``ir.mail_server``, matched on the address or its domain): no
per-team IMAP/SMTP setup. The reply keeps its RFC822 Message-Id, so the
customer's answer threads back into the same conversation through the ordinary
mail gateway.

A message already delivered through the alias is also recognised when the same
mail is filed a second time from the inbox viewer.
""",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "conversation_base",
        "conversation_email_base",
    ],
    "data": [
        "views/mail_conversation_team_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "conversation_team_inbox/static/tests/tours/**/*",
        ],
    },
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
