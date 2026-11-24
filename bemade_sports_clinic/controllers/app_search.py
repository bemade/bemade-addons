"""Task 1650 — the app header's search (the magnifier): the clinic's
providers.

Task 5200 (kit P5): the route (``GET /my/app/search?q=…``, an HTML
fragment), the sheet, the matching rule and the row layout are the kit's
(``PortalKitShell.pk_app_search``, ``bemade_portal_kit.tools.match``); the
clinic registers three providers through ``portal.kit._pk_search_providers``
(models/sc_app_roles.py): players, teams and events matching the typed
text, ~8 each.

* Players: first / last name only — accent- and case-insensitive, every
  typed word the start of a word of the name (« andy cous » finds
  Cousineau, Andy). Scope like the Joueurs page (/my/players): the viewer's
  players (staffed teams; every team for a clinic admin); a therapist also
  finds other teams' players by name, LOCKED (not openable, no detail but the
  name and the teams) with « Add to team » = the Joueurs page's guarded
  action. Archived players come last, greyed, marked « Archived ».
* Teams: the accessible teams (/my/teams), by team or organization name.
* Events: the events the viewer may see (/my/events), by name; upcoming
  first, then the recent past.
* Never more than the name, the team(s), the jersey / the date: no date of
  birth, phone or medical data.
"""
from urllib.parse import urlencode

from odoo import _, fields
from odoo.http import request
from odoo.tools import format_datetime

from odoo.addons.bemade_portal_kit.tools import pk_fold, pk_name_matches

from ..models.sc_name_match import NEAR, NameIndex
from .team_staff_portal import TeamStaffPortal

SEARCH_LIMIT = 8


class AppSearchPortal(TeamStaffPortal):

    def _sc_search_players(self, words):
        env = request.env
        user = env.user
        admin = self._is_clinic_admin()
        is_tp_admin = admin or user.has_group('base.group_system') or self._is_treatment_professional()
        Patients = env['sports.patient'].with_context(active_test=False)
        own_domain = self._prepare_players_domain(self._prepare_teams_domain())
        fields_read = ['first_name', 'last_name', 'active']
        own = {row['id']: row for row in Patients.search_read(own_domain, fields_read)}
        candidates = dict(own)
        if is_tp_admin:
            # The Joueurs page's broadened name search (identity only) —
            # active players only outside the user's own teams: the Joueurs
            # page never lists an archived out-of-team player (adversarial
            # review 2026-10-22); a clinic admin's scope is everything.
            broad = [] if admin else [('active', '=', True)]
            for row in Patients.sudo().search_read(broad, fields_read):
                candidates.setdefault(row['id'], row)
        # Task 1674: the shared matcher — #1650's word prefixes, then the
        # near matches (accents, typos, inversions) as « Close results ».
        grades = dict(NameIndex([(rid, row['first_name'] or '', row['last_name'] or '')
                                 for rid, row in candidates.items()]).match_words(words))
        records = env['sports.patient'].sudo().with_context(active_test=False).browse(list(grades))
        rows = []
        for player in records:
            teams = player.team_ids
            # Openable = the Joueurs page's rule: the viewer's own players
            # (staffed teams), any player for a clinic admin.
            accessible = admin or player.id in own
            rows.append({
                'id': player.id,
                'title': player._portal_list_name(),
                'subtitle': ', '.join(teams.mapped('name')),
                'archived': not player.active,
                'archived_label': _("Archived player"),
                'locked': not accessible,
                'url': '/my/player?player_id=%s' % player.id if accessible else False,
                # « Add to team »: the Joueurs page's own guarded action, on
                # its name search for this player.
                'action_label': False if accessible else _("Add to team"),
                'action_url': False if accessible else '/my/players?%s' % urlencode({
                    'first_name': player.first_name or '', 'last_name': player.last_name or ''}),
                'near': grades[player.id] == NEAR,
                'sort': (not player.active, not accessible, pk_fold(player.last_name), pk_fold(player.first_name)),
            })
        rows.sort(key=lambda r: r['sort'])
        return ([r for r in rows if not r['near']][:SEARCH_LIMIT]
                + [r for r in rows if r['near']][:SEARCH_LIMIT])

    def _sc_search_teams(self, words):
        rows = []
        for team in self._get_accessible_teams():
            if pk_name_matches(words, team.name) or pk_name_matches(words, team.parent_id.name or ''):
                rows.append({'id': team.id, 'title': team.name,
                             'subtitle': team.parent_id.name or '',
                             'url': '/my/team?team_id=%s' % team.id})
                if len(rows) >= SEARCH_LIMIT:
                    break
        return rows

    def _sc_search_events(self, words):
        env = request.env
        Events = env['sports.event']
        domain = list(self._prepare_events_domain())
        for word in words:
            domain.append(('name', 'ilike', word))
        now = fields.Datetime.now()
        events = Events.search(domain + [('date_start', '>=', now)], order='date_start asc', limit=50)
        events |= Events.search(domain + [('date_start', '<', now)], order='date_start desc', limit=50)
        rows = []
        for event in events:
            if not pk_name_matches(words, event.name):
                continue
            rows.append({'id': event.id, 'title': event.name,
                         'subtitle': self._sc_search_date(event),
                         'url': '/my/event/%s' % event.id})
            if len(rows) >= SEARCH_LIMIT:
                break
        return rows

    @staticmethod
    def _sc_search_date(event):
        return format_datetime(request.env, event.date_start, dt_format='short') if event.date_start else ''
