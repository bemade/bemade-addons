# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5200 (kit P5) — in-app help: the page key -> help article mapping.

Every app page has a help KEY (``portal.kit._pk_help_keys()``: page ->
key, else the page's own key). The app bar's « ? » opens the article mapped
to the key — the exact key, else its base (the part before the first dot),
else the help home — in a new tab. A page whose key is in
``portal.kit._pk_help_tabbed()`` refines it with its active tab
(« <key>.<tab> »; ``pk_help.js`` follows the tab switches). The user
menu's « Help » and « More »'s « User guide » open the help home
(``bemade_portal_kit.help_home_url``, Settings › Portal App).

URLs: an absolute ``https://`` address or a site-relative path (``/…``,
never ``//…``). ``portal.kit._pk_help_url(url)`` resolves each one (a
consumer may rewrite it, or answer False for a link that cannot open in
this database: the entry is then left out). Nothing is mapped by default.
"""
import json
import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_URL_RE = re.compile(r'^(https://[^\s"<>]+|/(?![/\\])[^\s"<>]*)$')


def pk_help_url_ok(url):
    """A help URL: ``https://…`` or a site-relative path, nothing else."""
    url = (url or '').strip()
    return bool(url and _URL_RE.match(url) and not url.lower().startswith('/javascript'))


class PortalKitHelp(models.Model):
    _name = 'portal.kit.help'
    _description = 'App help: page key to help article'
    _order = 'sequence, key, id'

    key = fields.Char(required=True, help="The page's help key (e.g. « settings », « account »).")
    url = fields.Char(string='Article URL', required=True,
                      help="The help article: an https address or a site path (/…).")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    note = fields.Char(help="Internal note (e.g. the article's title).")

    _key_unique = models.Constraint('UNIQUE(key)', 'One article per page key.')

    @api.constrains('url')
    def _check_url(self):
        for rec in self:
            if not pk_help_url_ok(rec.url):
                raise ValidationError(_("The help link must be an https address or a site path (/…)."))

    @api.model
    def _pk_resolve(self, url):
        url = (url or '').strip()
        if not pk_help_url_ok(url):
            return False
        return self.env['portal.kit']._pk_help_url(url) or False

    @api.model
    def pk_help_links(self):
        """``{'home': url|False, 'map': {key: url}}`` — the links that open
        here only (sudo: the mapping is configuration, read by every app
        user through this helper only)."""
        links = {}
        for rec in self.sudo().search([]):
            url = self._pk_resolve(rec.url)
            if url:
                links[rec.key] = url
        return {'home': self._pk_resolve(self.env['portal.kit'].pk_help_home()), 'map': links}

    @api.model
    def pk_help_for(self, page, tab=None):
        """The help of an app page: ``{'key', 'base', 'url', 'home',
        'map_json', 'tabbed'}``; ``url`` False when nothing applies (no
        « ? » then)."""
        kit = self.env['portal.kit']
        links = self.pk_help_links()
        base = kit._pk_help_page_key(page)
        tabbed = base in kit._pk_help_tabbed()
        key = '%s.%s' % (base, tab) if tab and tabbed else base
        url = links['map'].get(key) or links['map'].get(key.split('.')[0]) or links['home']
        return {
            'key': key,
            'base': base,
            'url': url or False,
            'home': links['home'],
            'map_json': json.dumps(links['map']),
            'tabbed': tabbed,
        }
