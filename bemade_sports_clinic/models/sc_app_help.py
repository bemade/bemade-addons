"""Task 1660 / 5200 (kit P5) — the clinic's in-app help.

The mapping model, the « ? » of the app bar, the user menu's « Aide » and
« Plus › Guide d'utilisation » are the kit's (``portal.kit.help``,
bemade_portal_kit; edited in Administration › Aide de l'application). The
clinic brings, through the kit's hooks on ``portal.kit``:

* its app's ``help_keys`` (its pages' help keys, ``SC_HELP_KEYS``) and
  ``help_tabbed`` (the player and team pages refine the key with their tab,
  « player.injuries »), task 5391: the kit's per-app registration
  (``_pk_apps``);
* ``_pk_help_url``: the user guide is website_knowledge's public pages
  (``/knowledge/article/<id>``, a SOFT dependency, Enterprise): such a link
  is offered only while website_knowledge is installed, and opens through
  the app's ``/my/guide/<id>`` (task 1720, controllers/knowledge_public.py).
  An app URL (``/my…``) is never a help link (the app shell intercepts it).
* Task 1685: the public guide view's header for a logged-in user.
"""
import re

from odoo import api, models

from .sc_app_nav import SC_APP

# App-shell page template -> help key.
SC_HELP_KEYS = {
    'sc_app_home': 'home',
    'sc_app_teams': 'teams',
    'sc_app_team': 'team',
    'sc_app_team_digest': 'team',
    'sc_app_team_digest_history': 'team',
    'sc_app_players': 'players',
    'sc_app_player': 'player',
    'sc_app_player_create': 'players',
    'sc_app_injury_new': 'injury',
    'sc_app_treatment_notes': 'player.notes',
    'sc_app_notepad': 'notepad',
    'sc_app_activities': 'activities',
    'sc_app_activity_detail': 'activities',
    'sc_app_activity_form': 'activities',
    'sc_app_events': 'events',
    'sc_app_event': 'event',
    'sc_app_event_form': 'event',
    'sc_app_events_calendar': 'calendar',
    'sc_app_timesheets': 'timesheets',
    'sc_app_clinics': 'clinics',
    'sc_app_clinic': 'clinic',
    # Task 5201 (kit P6): pk_app_install -> 'install' is bemade_portal_kit_pwa's.
}
# Pages whose help key carries their tab (« player.injuries »).
SC_HELP_TABBED = ('player', 'team')

# Task 1685: the public guide view's header for a logged-in user (see
# ScHelpArticle._sc_sync_knowledge_public_view). Review round 1 (2026-10-26):
# on a phone (< 576 px, Bootstrap's sm) the link is « ← App » (the full
# label stays its title / aria-label) and the title truncates with an
# ellipsis in the space left — Bootstrap utilities only, the public view's
# bundle (website_knowledge.assets_public_knowledge) carries them. The two
# labels are <div>s (inline by class) so each is its own translation term.
SC_KNOWLEDGE_PUBLIC_PARENT = 'website_knowledge.article_public_content'
SC_KNOWLEDGE_PUBLIC_VIEW = 'bemade_sports_clinic.sc_knowledge_public_back_to_app'
SC_KNOWLEDGE_PUBLIC_ARCH = """<data>
    <xpath expr="//div[hasclass('o_knowledge_public_virality')]" position="attributes">
        <attribute name="t-if">not request or request.env.user._is_public()</attribute>
    </xpath>
    <xpath expr="//div[hasclass('o_knowledge_public_virality')]" position="after">
        <div t-if="request and not request.env.user._is_public()"
             class="o_knowledge_public_virality nav-item text-center o_no_autohide_item flex-shrink-0 ms-2"
             data-sc-guide-back="1">
            <a href="/my" class="nav-link fw-bold text-nowrap" title="Back to the app" aria-label="Back to the app">
                <i class="fa fa-arrow-left me-1 d-sm-none" aria-hidden="true"/>
                <div class="d-none d-sm-inline">Back to the app</div>
                <div class="d-inline d-sm-none">App</div>
            </a>
        </div>
    </xpath>
    <xpath expr="//div[hasclass('o_knowledge_article_display_name')]/span[@t-if]" position="attributes">
        <attribute name="class" add="text-truncate" separator=" "/>
    </xpath>
    <xpath expr="//div[hasclass('o_knowledge_article_display_name')]/span[@t-else]" position="attributes">
        <attribute name="class" add="text-truncate" separator=" "/>
    </xpath>
</data>"""

# Task 1720: a configured /knowledge/article/<id> opens through the app's
# /my/guide/<id> (the public guide view for every logged-in user).
_KNOWLEDGE_ARTICLE_RE = re.compile(r'^/knowledge/article/(\d+)')


class SportsClinicHelp(models.AbstractModel):
    _inherit = 'portal.kit'

    @api.model
    def _pk_apps(self):
        apps = dict(super()._pk_apps())
        app = dict(apps.get(SC_APP) or {})
        app.update({'help_keys': SC_HELP_KEYS, 'help_tabbed': SC_HELP_TABBED})
        apps[SC_APP] = app
        return apps

    @api.model
    def _pk_help_page_key(self, page):
        """A clinic page not listed uses its name without « sc_app_ »."""
        if page and page.startswith('sc_app_') and page not in SC_HELP_KEYS:
            return page.removeprefix('sc_app_')
        return super()._pk_help_page_key(page)

    @api.model
    def _pk_help_url(self, url):
        """A /knowledge/… page needs website_knowledge (soft dependency) and
        opens through /my/guide/<id>; an app URL is never a help link (in
        the clinic's app)."""
        url = super()._pk_help_url(url)
        if not self._sc_is_app():
            return url
        if not url or url.startswith('/my') or 'subpath=knowledge' in url:
            return False
        if url.startswith('/knowledge/'):
            module = self.env['ir.module.module'].sudo()._get('website_knowledge')
            if not module or module.state != 'installed':
                return False
            return _KNOWLEDGE_ARTICLE_RE.sub(r'/my/guide/\1', url, count=1)
        return url

    # ------------------------------------------------------------------
    # Task 1685: the public guide view's header for a logged-in user
    # ------------------------------------------------------------------
    @api.model
    def _sc_sync_knowledge_public_view(self):
        """Create / refresh the extension of website_knowledge's public
        article header: a logged-in (portal) user gets « Back to the app »
        (/my) instead of « Sign in »; a public visitor keeps « Sign in ».

        website_knowledge is a soft dependency, so the view cannot sit in a
        data file (its parent may not exist). This runs on every install /
        update of the module (data/sc_knowledge_public_view.xml): the view
        is (re)written and its xmlid marked loaded, so the update keeps it —
        and drops it when website_knowledge is gone. Its French term loads
        with the module's translations, like any view of the module."""
        module = self.env['ir.module.module'].sudo()._get('website_knowledge')
        parent = self.env.ref(SC_KNOWLEDGE_PUBLIC_PARENT, raise_if_not_found=False)
        if not module or module.state != 'installed' or not parent:
            return False
        vals = {
            'name': 'Sports Clinic: public guide header (logged-in user)',
            'type': 'qweb',
            'key': SC_KNOWLEDGE_PUBLIC_VIEW,
            'inherit_id': parent.id,
            'mode': 'extension',
            'priority': 99,
            'arch_db': SC_KNOWLEDGE_PUBLIC_ARCH,
        }
        view = self.env.ref(SC_KNOWLEDGE_PUBLIC_VIEW, raise_if_not_found=False)
        View = self.env['ir.ui.view'].sudo()
        if view:
            view.sudo().write(vals)
        else:
            view = View.create(vals)
            self.env['ir.model.data'].sudo()._update_xmlids([{
                'xml_id': SC_KNOWLEDGE_PUBLIC_VIEW, 'record': view, 'noupdate': False,
            }])
        self.pool.loaded_xmlids.add(SC_KNOWLEDGE_PUBLIC_VIEW)
        return view
