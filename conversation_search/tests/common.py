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

from odoo.tests import TransactionCase


class ConversationSearchCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Conversation = cls.env["mail.conversation"]
        cls.backend = cls.env["conversation.search.backend"]
        cls.conv_a = cls.Conversation.create({"name": "Conv A"})
        cls.msg_a = cls.conv_a.message_post(
            body=Markup(
                "<div><p>Réunion pour la <b>pompe</b> centrifuge électricité</p></div>"
            ),
            subject="Soumission ACME",
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        cls.conv_b = cls.Conversation.create({"name": "Conv B"})
        cls.msg_b = cls.conv_b.message_post(
            body="Livraison prévue jeudi, pompe doseuse",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        cls.conv_c = cls.Conversation.create({"name": "Conv C"})
        cls.msg_c = cls.conv_c.message_post(
            body="quarterly report attached, see summary",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        cls.conv_oeuvre = cls.Conversation.create({"name": "Conv Oeuvre"})
        cls.conv_oeuvre.message_post(
            body=Markup("<p>Œuvre complète</p>"),
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        cls.partner = cls.env["res.partner"].create({"name": "Zanzibar Partner"})
        cls.partner.message_post(
            body="unique word zanzibarxyz here",
            message_type="comment",
            subtype_xmlid="mail.mt_note",
        )
        cls.all_convs = cls.Conversation.search([])

    def search_domain(self, query, user=None, convs=None):
        model = self.Conversation.with_user(user) if user else self.Conversation
        return model.search([("message_content", "ilike", query)])

    def search_api(self, query, user=None, **kw):
        model = self.Conversation.with_user(user) if user else self.Conversation
        return model._search_by_message_content(query, **kw)
