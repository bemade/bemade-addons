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
from odoo import api, fields, models
from odoo.fields import Domain

_POSITIVE_OPERATORS = ("ilike", "like", "=", "=ilike", "=like")


class MailConversation(models.Model):
    _inherit = "mail.conversation"

    message_content = fields.Char(
        string="Message Content",
        compute="_compute_message_content",
        search="_search_message_content_field",
        help="Search-only field: matches conversations having at least one "
        "message (subject or body text) containing the typed words. Supports "
        'quoted "phrases", OR and -exclusion. Case and accent insensitive.',
    )

    def _compute_message_content(self):
        for conversation in self:
            conversation.message_content = False

    @api.model
    def _search_message_content_field(self, operator, value):
        """Search method of ``message_content``.

        Accepts ``ilike``/``like``/``=``/``=ilike``/``=like`` and ``in``
        (union of several queries) with string values; every other operator
        returns ``NotImplemented`` so the ORM negates the positive form."""
        backend = self.env["conversation.search.backend"]
        if operator in _POSITIVE_OPERATORS and isinstance(value, str):
            return backend._search_domain(value)
        if operator == "in" and isinstance(value, (list, tuple, set)):
            texts = [v for v in value if isinstance(v, str)]
            return (
                Domain.OR(Domain(backend._search_domain(t)) for t in texts)
                if (texts)
                else [("id", "in", [])]
            )
        return NotImplemented

    @api.model
    def _search_by_message_content(self, query, domain=None, limit=80, offset=0):
        """Ranked full-text search over the messages owned by conversations.

        :param str query: free text (``websearch`` syntax: words are ANDed,
            ``"phrase"``, ``OR``, ``-exclusion``); case and accent
            insensitive.
        :param domain: optional extra domain restricting the conversations
            (access rules always apply, nothing runs as superuser).
        :return: list of dicts ``{conversation_id, rank, last_match_date,
            message_ids}`` ordered by relevance then recency. Empty for an
            empty or malformed query.
        """
        return self.env["conversation.search.backend"]._search_ranked(
            query, domain=domain, limit=limit, offset=offset
        )
