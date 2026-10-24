"""Task 1660 — in-app help: the page → user-guide article mapping.

Every app-shell page renders a stable help KEY (``SC_HELP_KEYS``: the page
template → key; the player and team pages add their tab, « player.injuries »).
The « ? » of the app bar opens the article mapped to that key — the exact key,
else its base (« player »), else the guide home — in a new tab. The user menu's
« Aide » and the « Plus » row « Guide d'utilisation » open the guide home.

* The mapping (``sc.help.article``) is edited in the back end by the clinic
  administrators (Administration › Aide de l'application); nothing is mapped
  by default — production article ids differ from staging's.
* The guide home is the system parameter ``bemade_sports_clinic.help_home_url``
  (empty by default: then, with no mapping either, no help entry shows).
* URLs are the PUBLIC website_knowledge pages (``/knowledge/article/<id>``) or
  an absolute https address — never an app URL (``/my…``: the app shell
  intercepts it). A ``/knowledge/…`` URL is offered only while
  ``website_knowledge`` is installed (soft dependency: no manifest dependency).
* No data in the URL beyond the page key's article.
"""
import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

SC_HELP_HOME_PARAM = 'bemade_sports_clinic.help_home_url'

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
    'sc_app_settings': 'settings',
    'sc_app_account': 'account',
    'sc_app_security': 'account',
    'sc_app_install': 'install',
    'sc_app_more': 'home',
    'sc_app_search_results': 'search',
}
# Pages whose help key carries their tab (« player.injuries »).
SC_HELP_TABBED = ('player', 'team')

_URL_RE = re.compile(r'^(https://[^\s"<>]+|/knowledge/article/\d+[^\s"<>]*)$')


def sc_help_url_ok(url):
    """A help URL: a public Knowledge page or an absolute https address —
    never an app URL nor a script."""
    url = (url or '').strip()
    return bool(url and _URL_RE.match(url) and 'subpath=knowledge' not in url)


class ScHelpArticle(models.Model):
    _name = 'sc.help.article'
    _description = 'App help: page to guide article'
    _order = 'sequence, key, id'

    key = fields.Char(
        required=True,
        help="The page's help key: home, teams, team, team.players, players, player, "
             "player.injuries, player.info, player.documents, player.notes, "
             "player.activities, injury, notepad, activities, events, event, calendar, "
             "timesheets, clinics, clinic, settings, account, install, search.")
    url = fields.Char(
        string='Article URL', required=True,
        help="The public guide article: /knowledge/article/<id> (or an https address).")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Char(help="Internal note (e.g. the article's title).")

    _key_unique = models.Constraint('UNIQUE(key)', 'One article per page key.')

    @api.constrains('url')
    def _check_url(self):
        for rec in self:
            if not sc_help_url_ok(rec.url):
                raise ValidationError(_(
                    "The help link must be a public guide article (/knowledge/article/<id>) "
                    "or an https address."))

    @api.model
    def _sc_url_available(self, url):
        """A /knowledge/… page needs website_knowledge (soft dependency)."""
        if not sc_help_url_ok(url):
            return False
        if url.startswith('/knowledge/'):
            module = self.env['ir.module.module'].sudo()._get('website_knowledge')
            return bool(module) and module.state == 'installed'
        return True

    @api.model
    def _sc_help_links(self):
        """``{'home': url|False, 'map': {key: url}}`` — the available links
        only (sudo: the mapping is configuration, readable by every app
        user through this helper only)."""
        home = (self.env['ir.config_parameter'].sudo().get_param(SC_HELP_HOME_PARAM) or '').strip()
        links = {
            rec.key: rec.url.strip()
            for rec in self.sudo().search([])
            if self._sc_url_available(rec.url.strip())
        }
        return {'home': home if self._sc_url_available(home) else False, 'map': links}

    @api.model
    def _sc_help_for(self, page, tab=None):
        """The help of an app page: ``{'key', 'url', 'home', 'map_json'}``;
        ``url`` False when nothing applies (no entry is shown then)."""
        links = self._sc_help_links()
        base = SC_HELP_KEYS.get(page) or (page or '').removeprefix('sc_app_') or 'home'
        key = '%s.%s' % (base, tab) if tab and base in SC_HELP_TABBED else base
        url = links['map'].get(key) or links['map'].get(key.split('.')[0]) or links['home']
        return {
            'key': key,
            'base': base,
            'url': url or False,
            'home': links['home'],
            'map_json': json.dumps(links['map']),
        }
