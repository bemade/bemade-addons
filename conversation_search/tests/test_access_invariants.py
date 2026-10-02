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
from odoo.tests import tagged

from .common import ConversationSearchCase


@tagged("post_install", "-at_install")
class TestAccessInvariants(ConversationSearchCase):
    def test_restricted_user_only_sees_readable_conversations(self):
        restricted = self.env["res.users"].create(
            {
                "name": "Restricted",
                "login": "restricted_search",
                "group_ids": [(6, 0, [self.env.ref("base.group_user").id])],
            }
        )
        conv_a2 = self.Conversation.create({"name": "A2"})
        conv_a2.message_post(
            body="autre pompe",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.conv_a.user_id = restricted
        self.env["ir.rule"].create(
            {
                "name": "conversation_search test: own conversations",
                "model_id": self.env["ir.model"]._get("mail.conversation").id,
                "groups": [(6, 0, [self.env.ref("base.group_user").id])],
                "domain_force": f"[('user_id', '=', {restricted.id})]",
            }
        )
        self.assertEqual(self.search_domain("pompe", user=restricted), self.conv_a)
        rows = self.search_api("pompe", user=restricted)
        self.assertEqual([r["conversation_id"] for r in rows], [self.conv_a.id])
        unreadable = (self.msg_b | conv_a2.message_ids).ids
        for row in rows:
            self.assertFalse(set(row["message_ids"]) & set(unreadable))

    def test_non_conversation_message_is_not_indexed(self):
        self.env.cr.execute(
            "SELECT count(*) FROM mail_message WHERE model = 'res.partner' "
            "AND conversation_search_tsv(subject, body) @@ "
            "websearch_to_tsquery('simple', 'zanzibarxyz')"
        )
        self.assertEqual(self.env.cr.fetchone()[0], 1)  # function works on any row
        self.assertFalse(self.search_domain("zanzibarxyz"))

    def test_no_column_added_to_mail_message(self):
        self.assertFalse(
            [
                name
                for name, field in self.env["mail.message"]._fields.items()
                if field.store and (field._module == "conversation_search")
            ]
        )

    def test_uninstall_hook_cleans_up(self):
        from odoo.addons.conversation_search.hooks import uninstall_hook

        self.env["ir.config_parameter"].sudo().set_param(
            "conversation_search.backend", "fts"
        )
        uninstall_hook(self.env)
        cr = self.env.cr
        cr.execute(
            "SELECT 1 FROM pg_indexes WHERE indexname = "
            "'conversation_search_mail_message_tsv_idx'"
        )
        self.assertFalse(cr.fetchone())
        cr.execute(
            "SELECT 1 FROM pg_proc WHERE proname IN "
            "('conversation_search_tsv', 'conversation_search_fold')"
        )
        self.assertFalse(cr.fetchone())
        self.assertFalse(
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("conversation_search.backend")
        )
        self.conv_a.message_post(
            body="après", message_type="comment", subtype_xmlid="mail.mt_note"
        )
        self.assertIn(
            self.msg_a,
            self.env["mail.message"].search([("body", "ilike", "centrifuge")]),
        )
        self.backend.init()
