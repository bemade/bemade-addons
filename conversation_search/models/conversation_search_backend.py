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
import logging
import re

from odoo import api, models

_logger = logging.getLogger(__name__)

PARAM_KEY = "conversation_search.backend"
DEFAULT_BACKEND = "fts"
_WORD_RE = re.compile(r"\w", re.UNICODE)


class ConversationSearchBackend(models.AbstractModel):
    """The ONE search-backend interface for conversation messages.

    Callers (the ``mail.conversation`` entry points, the search view, later
    slices) only ever use the four public operations below; they never touch
    a backend's storage or query language. Exactly one backend is active per
    database, selected by the ``conversation_search.backend`` system
    parameter (default ``fts``). The code is validated against
    :meth:`_get_backends`, and each operation dispatches to
    ``_<operation>_<code>`` -- the same guarded dispatch-on-a-value style as
    ``conversation.transport`` providers, so module load order never decides
    which backend runs.

    Plugging in a backend (06b attachments, 06c pgvector, Elasticsearch)::

        class MyBackend(models.AbstractModel):
            _inherit = "conversation.search.backend"

            @api.model
            def _get_backends(self):
                return super()._get_backends() + [("my", "My backend")]

            @api.model
            def _search_domain_my(self, text): ...
            @api.model
            def _search_ranked_my(self, text, domain=None, limit=80, offset=0): ...
            @api.model
            def _index_messages_my(self, messages): ...
            @api.model
            def _rebuild_index_my(self): ...

    Contract of the operations:

    ``_search_domain(text)``
        Returns a ``mail.conversation`` domain selecting conversations with
        at least one owned message matching the free-text query. Must
        return a domain matching nothing for an empty / punctuation-only
        query, and must never raise on malformed input. No ``sudo()``:
        access is enforced by the ORM search that consumes the domain.

    ``_search_ranked(text, domain=None, limit=80, offset=0)``
        Returns a list of dicts ``{"conversation_id", "rank",
        "last_match_date", "message_ids"}`` ordered by relevance then
        recency, restricted to conversations the current user can read
        within ``domain``. ``message_ids`` are matching messages the
        current user can read.

    ``_index_messages(messages)``
        Refresh the index for the given ``mail.message`` records. A backend
        whose index is maintained synchronously by the database may make
        this a no-op.

    ``_rebuild_index()``
        (Re)build the whole index; must be idempotent.
    """

    _name = "conversation.search.backend"
    _description = "Conversation Search Backend"

    # ------------------------------------------------------------------
    # Registry / selection
    # ------------------------------------------------------------------
    @api.model
    def _get_backends(self):
        """Return the ``[(code, label)]`` registry of known backends.

        Extend with ``super()`` like ``selection_add``."""
        return [(DEFAULT_BACKEND, "PostgreSQL full-text")]

    @api.model
    def _get_active_backend(self):
        """Return the active backend code (configured, else ``fts``).

        An unknown configured value logs a warning and falls back to
        ``fts`` so a stale parameter can never break search."""
        code = (
            self.env["ir.config_parameter"].sudo().get_param(PARAM_KEY)
            or DEFAULT_BACKEND
        )
        if code not in dict(self._get_backends()):
            _logger.warning(
                "Unknown conversation search backend %r, falling back to %r",
                code,
                DEFAULT_BACKEND,
            )
            code = DEFAULT_BACKEND
        return code

    @api.model
    def _dispatch(self, op, *args, **kwargs):
        code = self._get_active_backend()
        method = getattr(self, f"_{op}_{code}", None)
        if method is None:
            raise NotImplementedError(
                f"Conversation search backend {code!r} does not implement {op!r}"
            )
        return method(*args, **kwargs)

    @api.model
    def _is_empty_query(self, text):
        """True when the query has no word character at all."""
        return not isinstance(text, str) or not _WORD_RE.search(text)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------
    @api.model
    def _search_domain(self, text):
        """Domain on ``mail.conversation`` matching the free-text query."""
        if self._is_empty_query(text):
            return [("id", "in", [])]
        return self._dispatch("search_domain", text)

    @api.model
    def _search_ranked(self, text, domain=None, limit=80, offset=0):
        """Ranked results, see the class docstring."""
        if self._is_empty_query(text):
            return []
        return self._dispatch(
            "search_ranked", text, domain=domain, limit=limit, offset=offset
        )

    @api.model
    def _index_messages(self, messages):
        """Refresh the index for ``messages``."""
        return self._dispatch("index_messages", messages)

    @api.model
    def _rebuild_index(self):
        """Rebuild the whole index (idempotent)."""
        return self._dispatch("rebuild_index")
