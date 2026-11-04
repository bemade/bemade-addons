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
from markupsafe import Markup

from odoo.tests import tagged

from .common import ConversationSearchCase

INDEX = "conversation_search_mail_message_tsv_idx"


@tagged("post_install", "-at_install")
class TestFreshnessBackfill(ConversationSearchCase):
    def _index_exists(self):
        self.env.cr.execute("SELECT 1 FROM pg_indexes WHERE indexname = %s", [INDEX])
        return bool(self.env.cr.fetchone())

    def test_same_transaction_freshness(self):
        self.conv_c.message_post(
            body="nouveau mot fraisier",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.assertEqual(self.search_domain("fraisier"), self.conv_c)
        self.assertEqual(
            [r["conversation_id"] for r in self.search_api("fraisier")],
            [self.conv_c.id],
        )

    def test_edit_updates_matches(self):
        self.msg_c.sudo().write({"body": Markup("<p>remplacé framboise</p>")})
        self.assertEqual(self.search_domain("framboise"), self.conv_c)
        self.assertFalse(self.search_domain("quarterly"))

    def test_delete_removes_matches(self):
        self.msg_c.sudo().unlink()
        self.assertFalse(self.search_domain("quarterly"))

    def test_split_move_attributes_to_new_conversation(self):
        conv_d = self.Conversation.create({"name": "Conv D"})
        self.msg_c.sudo().write({"res_id": conv_d.id})
        self.assertEqual(self.search_domain("quarterly"), conv_d)
        rows = self.search_api("quarterly")
        self.assertEqual([r["conversation_id"] for r in rows], [conv_d.id])
        self.assertEqual(rows[0]["message_ids"], [self.msg_c.id])

    def test_backfill_and_idempotence(self):
        self.env.cr.execute(f"DROP INDEX {INDEX}")
        self.conv_c.message_post(
            body="avant reconstruction cerise",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.backend.init()
        self.assertTrue(self._index_exists())
        first = self.search_api("cerise")
        self.assertEqual([r["conversation_id"] for r in first], [self.conv_c.id])
        self.backend.init()
        self.backend._rebuild_index()
        self.assertTrue(self._index_exists())
        self.assertEqual(self.search_api("cerise"), first)

    def test_version_change_triggers_reindex(self):
        self.env.cr.execute(
            "COMMENT ON FUNCTION conversation_search_tsv(text, text) IS 'stale'"
        )
        self.backend._fts_ensure_index()
        self.env.cr.execute(
            "SELECT obj_description(p.oid, 'pg_proc') FROM pg_proc p "
            "WHERE p.proname = 'conversation_search_tsv'"
        )
        self.assertEqual(self.env.cr.fetchone()[0], "conversation_search_fts_v1")

    def test_indexing_never_notifies(self):
        def counts():
            return [
                self.env[m].sudo().search_count([])
                for m in ("mail.mail", "mail.message", "mail.followers")
            ]

        subtype = self.env.ref("mail.mt_comment")
        before, stamp = counts(), subtype.write_date
        self.search_domain("centrifuge")
        self.search_domain("centrifuge OR quarterly")
        self.search_api("pompe")
        self.backend._rebuild_index()
        self.backend.init()
        self.assertEqual(counts(), before)
        subtype.invalidate_recordset()
        self.assertEqual(subtype.write_date, stamp)
