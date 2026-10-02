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
from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import ConversationSearchCase

BACKEND_CLASS = "odoo.addons.conversation_search.models.conversation_search_backend"


@tagged("post_install", "-at_install")
class TestBackendAbstraction(ConversationSearchCase):
    def _set_backend(self, code):
        self.env["ir.config_parameter"].sudo().set_param(
            "conversation_search.backend", code
        )

    def test_second_backend_serves_unchanged_callers(self):
        backend_cls = type(self.backend)
        original = backend_cls._get_backends
        dummy_rows = [
            {
                "conversation_id": self.conv_c.id,
                "rank": 1.0,
                "last_match_date": False,
                "message_ids": [],
            }
        ]

        def get_backends(model):
            return original(model) + [("dummy", "Dummy")]

        with (
            patch.object(backend_cls, "_get_backends", get_backends),
            patch.object(
                backend_cls,
                "_search_domain_dummy",
                lambda model, text: [("id", "=", self.conv_c.id)],
                create=True,
            ),
            patch.object(
                backend_cls,
                "_search_ranked_dummy",
                lambda model, text, domain=None, limit=80, offset=0: dummy_rows,
                create=True,
            ),
        ):
            self.assertEqual(self.search_domain("centrifuge"), self.conv_a)
            self._set_backend("dummy")
            self.assertEqual(self.search_domain("centrifuge"), self.conv_c)
            self.assertEqual(self.search_api("centrifuge"), dummy_rows)
            self._set_backend("fts")
            self.assertEqual(self.search_domain("centrifuge"), self.conv_a)

    def test_unknown_backend_falls_back_to_fts(self):
        self._set_backend("nope")
        with self.assertLogs(BACKEND_CLASS, level="WARNING") as logs:
            self.assertEqual(self.search_domain("centrifuge"), self.conv_a)
        self.assertTrue(any("nope" in line for line in logs.output))

    def test_unset_backend_defaults_to_fts(self):
        self.env["ir.config_parameter"].sudo().search(
            [("key", "=", "conversation_search.backend")]
        ).unlink()
        self.assertEqual(self.backend._get_active_backend(), "fts")

    def test_missing_operation_names_the_backend(self):
        backend_cls = type(self.backend)
        original = backend_cls._get_backends
        with patch.object(
            backend_cls,
            "_get_backends",
            lambda model: original(model) + [("half", "Half")],
        ):
            self._set_backend("half")
            with self.assertRaisesRegex(NotImplementedError, "half"):
                self.backend._rebuild_index()

    @mute_logger(BACKEND_CLASS)
    def test_view_builds_with_message_content_entry(self):
        views = self.Conversation.get_views([(False, "search")])
        self.assertIn('name="message_content"', views["views"]["search"]["arch"])
