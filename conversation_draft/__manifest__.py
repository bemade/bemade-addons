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
    "name": "Conversation Draft",
    "version": "19.0.1.1.0",
    "category": "Discuss",
    "summary": "Shared, collaboratively edited reply drafts on a conversation.",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "conversation_base",
        "html_editor",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/mail_conversation_draft_views.xml",
        "wizards/mail_conversation_draft_template_views.xml",
        "views/mail_conversation_views.xml",
        "views/mail_conversation_triage_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "conversation_draft/static/src/**/*",
        ],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
}
