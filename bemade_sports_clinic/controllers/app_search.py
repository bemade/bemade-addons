"""Task 1650 — the app header's search (the magnifier).

``GET /my/app/search?q=…`` answers an HTML fragment (the search sheet's body):
players, teams and events matching the typed text, grouped, ~8 each.

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
import re
import unicodedata
from urllib.parse import urlencode

from odoo import fields, http
from odoo.http import request
from odoo.tools import format_datetime

from .team_staff_portal import TeamStaffPortal

SEARCH_MIN = 2
SEARCH_LIMIT = 8
_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


def sc_fold(text):
    """Lower case, without accents (« Élodie » -> « elodie »)."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch)).casefold()


def sc_words(text):
    return _WORD_RE.findall(sc_fold(text))


def sc_name_matches(query_words, *names):
    """Every typed word is the start of a word of the name."""
    tokens = [token for name in names for token in sc_words(name)]
    return all(any(token.startswith(word) for token in tokens) for word in query_words)


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
        matched = [row for row in candidates.values()
                   if sc_name_matches(words, row['first_name'], row['last_name'])]
        records = env['sports.patient'].sudo().with_context(active_test=False).browse(
            [row['id'] for row in matched])
        rows = []
        for player in records:
            teams = player.team_ids
            # Openable = the Joueurs page's rule: the viewer's own players
            # (staffed teams), any player for a clinic admin.
            accessible = admin or player.id in own
            rows.append({
                'id': player.id,
                'title': player._portal_list_name(),
                'teams': ', '.join(teams.mapped('name')),
                'archived': not player.active,
                'accessible': accessible,
                'url': '/my/player?player_id=%s' % player.id if accessible else False,
                # « Add to team »: the Joueurs page's own guarded action, on
                # its name search for this player.
                'add_url': False if accessible else '/my/players?%s' % urlencode({
                    'first_name': player.first_name or '', 'last_name': player.last_name or ''}),
                'sort': (not player.active, not accessible, sc_fold(player.last_name), sc_fold(player.first_name)),
            })
        rows.sort(key=lambda r: r['sort'])
        return rows[:SEARCH_LIMIT]

    def _sc_search_teams(self, words):
        rows = []
        for team in self._get_accessible_teams():
            if sc_name_matches(words, team.name) or sc_name_matches(words, team.parent_id.name or ''):
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
            if not sc_name_matches(words, event.name):
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

    @http.route('/my/app/search', type='http', auth='user', methods=['GET'], multilang=False, sitemap=False)
    def sc_app_search(self, q='', **kw):
        query = (q or '').strip()
        words = sc_words(query)
        values = {'sc_query': query, 'sc_too_short': len(sc_fold(query).replace(' ', '')) < SEARCH_MIN}
        if not values['sc_too_short'] and words:
            values.update({
                'sc_players': self._sc_search_players(words),
                'sc_teams': self._sc_search_teams(words),
                'sc_events': self._sc_search_events(words),
            })
        html = request.env['ir.ui.view']._render_template(
            'bemade_sports_clinic.sc_app_search_results', values)
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8'),
                                                    ('Cache-Control', 'no-store')])
