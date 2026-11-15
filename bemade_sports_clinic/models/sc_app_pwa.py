# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5201 (kit P6): Fit Crew's installable app on bemade_portal_kit_pwa.

* ``sc_fill_pwa_branding(env)``: the company app fields (name, short name,
  colours, the 5 icons) get the Fit Crew values, ONLY where they are empty
  (an administrator's later edit is kept). Run by the install hook and the
  19.0.1.147.0 post-migration;
* the hooks: start URL (and manifest id) ``/my/home``, the Teams / Players
  shortcuts, the offline page's Fit Crew colours and fonts.
"""
import base64

from odoo import api, models
from odoo.tools import file_open

SC_PWA_IMG = 'bemade_sports_clinic/static/src/img/'
# The values installed apps had before the move (task 1542): the manifest
# must not change (an installed app keeps its name, colours and icons).
SC_PWA_VALUES = (
    ('pk_pwa_name', 'Le Fit Crew'),
    ('pk_pwa_short_name', 'Fit Crew'),
    ('pk_pwa_background_color', '#120e12'),
    ('pk_pwa_theme_color', '#120e12'),
)
SC_PWA_ICONS = (
    ('pk_pwa_icon_192', 'sc_icon_192.png'),
    ('pk_pwa_icon_512', 'sc_icon_512.png'),
    ('pk_pwa_icon_maskable_512', 'sc_icon_maskable_512.png'),
    ('pk_pwa_apple_touch_icon', 'sc_apple_touch_icon.png'),
    ('pk_pwa_logo', 'sc_logo_chrome.png'),
)


def sc_fill_pwa_branding(env):
    """Fill every company's empty app fields with Fit Crew's values.
    Returns ``{company id: [field, ...]}`` of what was written."""
    written = {}
    companies = env['res.company'].sudo().with_context(bin_size=True, active_test=False).search([])
    for company in companies:
        vals = {field: value for field, value in SC_PWA_VALUES if not company[field]}
        for field, filename in SC_PWA_ICONS:
            if not company[field]:
                with file_open(SC_PWA_IMG + filename, 'rb') as source:
                    vals[field] = base64.b64encode(source.read())
        if vals:
            company.write(vals)
            written[company.id] = sorted(vals)
    return written


class PortalKit(models.AbstractModel):
    _inherit = 'portal.kit'

    @api.model
    def _pk_pwa_start_url(self):
        # The dashboard; also the manifest id since task 1542 (never change
        # it: installed apps would become a second app).
        return '/my/home'

    @api.model
    def _pk_pwa_shortcuts(self):
        labels = self.pk_nav_labels()
        # The nav entries' labels (a registry without them, e.g. the kit's
        # own tests: no shortcut).
        return super()._pk_pwa_shortcuts() + [
            {'name': labels[key], 'url': url}
            for key, url in (('teams', '/my/teams'), ('players', '/my/players')) if key in labels
        ]

    @api.model
    def _pk_pwa_offline_style(self, pwa):
        style = dict(super()._pk_pwa_offline_style(pwa))
        # The offline page as Fit Crew had it (task 1542): Minuit, the neon
        # retry button, DM Sans / Teko (when the device has them).
        style.update({
            'bg': pwa['background_color'],
            'fg': '#e5e5e5',
            'muted': '#a9a8ae',
            'accent': '#a4c754',
            'accent-fg': '#120e12',
            'font': '"DM Sans", system-ui, -apple-system, "Segoe UI", Roboto, sans-serif',
            'title-font': '"Teko", "DM Sans", system-ui, sans-serif',
            'title-transform': 'uppercase',
            'title-spacing': '0.02em',
        })
        return style
