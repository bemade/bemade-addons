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


@tagged("post_install", "-at_install")
class TestFtsMatching(ConversationSearchCase):
    def test_single_word_body_domain_and_api(self):
        self.assertEqual(self.search_domain("centrifuge"), self.conv_a)
        rows = self.search_api("centrifuge")
        self.assertEqual([r["conversation_id"] for r in rows], [self.conv_a.id])
        self.assertIn(self.msg_a.id, rows[0]["message_ids"])

    def test_subject_is_indexed(self):
        self.assertEqual(self.search_domain("ACME"), self.conv_a)

    def test_and(self):
        self.assertEqual(self.search_domain("pompe centrifuge"), self.conv_a)
        self.assertEqual(self.search_domain("pompe"), self.conv_a | self.conv_b)

    def test_case_insensitive(self):
        self.assertEqual(self.search_domain("POMPE"), self.search_domain("pompe"))
        self.assertEqual(self.search_domain("POMPE"), self.conv_a | self.conv_b)

    def test_accents_both_directions(self):
        self.assertEqual(self.search_domain("reunion"), self.conv_a)
        self.assertEqual(self.search_domain("electricite"), self.conv_a)
        self.assertEqual(self.search_domain("RÉUNION"), self.conv_a)
        self.assertEqual(self.search_domain("prevue"), self.conv_b)
        self.assertEqual(self.search_domain("oeuvre"), self.conv_oeuvre)
        self.assertEqual(self.search_domain("ŒUVRE"), self.conv_oeuvre)

    def test_phrase(self):
        self.assertEqual(self.search_domain('"pompe centrifuge"'), self.conv_a)
        self.assertFalse(self.search_domain('"centrifuge pompe"'))

    def test_or(self):
        self.assertEqual(
            self.search_domain("centrifuge OR quarterly"), self.conv_a | self.conv_c
        )

    def test_exclusion(self):
        self.assertEqual(self.search_domain("pompe -doseuse"), self.conv_a)

    def test_html_markup_does_not_match(self):
        for word in ("div", "span", "p", "class", "b"):
            with self.subTest(word=word):
                self.assertFalse(self.search_domain(word))
                self.assertEqual(self.search_api(word), [])

    def test_html_entities_and_style_blocks_are_stripped(self):
        conv = self.Conversation.create({"name": "Styled"})
        conv.message_post(
            body=Markup(
                "<style>.mystyleclass {color: red}</style><p>caf&eacute; &amp; lait"
                "<!-- hiddencomment --></p>"
            ),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        self.assertFalse(self.search_domain("mystyleclass"))
        self.assertFalse(self.search_domain("hiddencomment"))
        self.assertFalse(self.search_domain("eacute"))
        self.assertEqual(self.search_domain("lait"), conv)

    def test_malformed_input(self):
        for query in ("", "   ", "!!!", '"', "-", "((", '""', "& | !", "- -"):
            with self.subTest(query=query):
                if query.strip():
                    # (the ORM itself short-circuits ``ilike ''`` to "all")
                    self.assertFalse(self.search_domain(query))
                self.assertFalse(
                    self.Conversation.search(self.backend._search_domain(query))
                )
                self.assertEqual(self.search_api(query), [])

    def test_negated_domain(self):
        found = self.Conversation.search(
            [("message_content", "not ilike", "centrifuge")]
        )
        self.assertIn(self.conv_b, found)
        self.assertIn(self.conv_c, found)
        self.assertNotIn(self.conv_a, found)

    def test_equals_and_in_operators(self):
        self.assertEqual(
            self.Conversation.search([("message_content", "=", "centrifuge")]),
            self.conv_a,
        )
        self.assertEqual(
            self.Conversation.search(
                [("message_content", "in", ["centrifuge", "quarterly"])]
            ),
            self.conv_a | self.conv_c,
        )
        self.assertFalse(self.Conversation.search([("message_content", "in", [])]))

    def test_other_models_never_match(self):
        self.assertFalse(self.search_domain("zanzibarxyz"))
        self.assertEqual(self.search_api("zanzibarxyz"), [])
        self.env.cr.execute(
            "SELECT indexdef FROM pg_indexes WHERE indexname = "
            "'conversation_search_mail_message_tsv_idx'"
        )
        self.assertIn("model)::text = 'mail.conversation'", self.env.cr.fetchone()[0])

    def test_ranking_prefers_more_relevant_then_recent(self):
        rows = self.search_api("pompe")
        self.assertEqual(
            {r["conversation_id"] for r in rows}, {self.conv_a.id, self.conv_b.id}
        )
        self.assertEqual(rows, sorted(rows, key=lambda r: -r["rank"]))
        self.assertEqual(len(self.search_api("pompe", limit=1)), 1)
        self.assertEqual(len(self.search_api("pompe", offset=1)), len(rows) - 1)

    def test_ranked_api_respects_extra_domain(self):
        rows = self.search_api("pompe", domain=[("id", "=", self.conv_b.id)])
        self.assertEqual([r["conversation_id"] for r in rows], [self.conv_b.id])
