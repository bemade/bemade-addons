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
import json

from odoo.tests import tagged
from odoo.tools import SQL

from .common import ConversationSearchCase

INDEX = "conversation_search_mail_message_tsv_idx"


@tagged("post_install", "-at_install")
class TestIndexPlanPerf(ConversationSearchCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cr = cls.env.cr
        cr.execute(
            """
            INSERT INTO mail_message
                   (model, res_id, message_type, body, subject, date,
                    create_date, write_date)
            SELECT 'mail.conversation',
                   (%s::int[])[1 + g %% %s],
                   'comment',
                   '<p>texte ' || md5(g::text) || ' commun'
                       || CASE WHEN g = 5000 THEN ' needleunique' ELSE '' END
                       || '</p>',
                   'Sujet ' || g, now(), now(), now()
              FROM generate_series(1, 10000) g
            """,
            [cls.all_convs.ids, len(cls.all_convs)],
        )
        cr.execute("ANALYZE mail_message")

    def _plan(self, sql):
        self.env.cr.execute(SQL("EXPLAIN (ANALYZE, FORMAT JSON) %s", sql))
        plan = self.env.cr.fetchone()[0]
        if isinstance(plan, str):
            plan = json.loads(plan)
        return plan[0]

    def _nodes(self, node):
        yield node
        for child in node.get("Plans", []):
            yield from self._nodes(child)

    def _assert_fast_indexed(self, sql, limit_ms=1000):
        plan = self._plan(sql)
        nodes = list(self._nodes(plan["Plan"]))
        self.assertIn(INDEX, {n.get("Index Name") for n in nodes})
        self.assertFalse(
            [
                n
                for n in nodes
                if n["Node Type"] == "Seq Scan"
                and n.get("Relation Name") == "mail_message"
            ]
        )
        self.assertLess(plan["Execution Time"], limit_ms)

    def test_domain_path_uses_gin_index(self):
        self.backend._fts_flush()
        query = self.Conversation._search(
            [("message_content", "ilike", "needleunique")]
        )
        self._assert_fast_indexed(query.select())

    def test_ranked_path_uses_gin_index_selective_term(self):
        self.backend._fts_flush()
        self._assert_fast_indexed(self.backend._fts_ranked_sql("needleunique"))

    def test_ranked_path_worst_case_all_rows_match(self):
        self.backend._fts_flush()
        plan = self._plan(self.backend._fts_ranked_sql("commun", limit=80))
        self.assertLess(plan["Execution Time"], 1000)
        self.assertEqual(
            len(self.search_api("commun", limit=80)),
            80 if len(self.all_convs) >= 80 else len(self.all_convs),
        )
