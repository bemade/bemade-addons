from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _
from odoo.exceptions import UserError


class TeamStaffPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        rtn = super()._prepare_home_portal_values(counters)
        teams_domain = self._prepare_teams_domain()
        players_domain = self._prepare_players_domain(teams_domain)
        activities_domain = self._prepare_activities_domain()
        rtn['teams_count'] = http.request.env['sports.team'].search_count(teams_domain)
        rtn['players_count'] = http.request.env['sports.patient'].search_count(
            players_domain)
        rtn['activities_count'] = http.request.env['mail.activity'].search_count(
            activities_domain)
        return rtn

    @classmethod
    def _prepare_teams_domain(cls):
        user = http.request.env.user
        return [
            ('staff_ids.user_ids', '=', user.id),
        ]

    @classmethod
    def _prepare_players_domain(cls, teams_domain):
        team_ids = http.request.env['sports.team'].search(teams_domain).ids
        return [
            ('team_ids', 'in', team_ids),
        ]

    @classmethod
    def _prepare_activities_domain(cls):
        user = http.request.env.user
        return [
            ('user_id', '=', user.id),
        ]

    @http.route(route=['/my/teams', '/my/teams/page/<int:page>'], type='http', auth='user', website=True)
    def view_teams(self, page=0, **kw):
        """ Display the list of teams that a portal user has access to """
        Teams = http.request.env['sports.team']
        domain = self._prepare_teams_domain()
        teams_count = Teams.search_count(domain)
        pgr = pager(url='/my/teams', total=teams_count,
                    page=page, step=10, scope=5)
        teams = http.request.env['sports.team'].search(self._prepare_teams_domain(),
                                                       offset=pgr['offset'],
                                                       limit=teams_count)
        return http.request.render(template='bemade_sports_clinic.portal_my_teams',
                                   qcontext={
                                       'teams_count': teams_count,
                                       'teams': teams,
                                       'pager': pgr,
                                       'page_name': 'my_teams',
                                   })

    @http.route(route=['/my/team', '/my/team/page/<int:page>'], type='http', auth='user', website=True)
    def view_team(self, team_id, page=0, **kw):
        """ Display the information for a team including its list of players """
        team_id = int(team_id)
        team = http.request.env['sports.team'].browse(team_id)
        if not team:
            raise UserError(_('This team could not be found.'))
        players_count = team.player_count
        pgr = pager(url=f'/my/team', total=players_count, page=page, step=10,
                    scope=5, url_args={'team_id': team_id})
        players = http.request.env['sports.patient'].search([
            ('team_ids', 'in', team_id),
        ], offset=pgr['offset'], limit=players_count)
        return http.request.render(
            template='bemade_sports_clinic.portal_my_team_players',
            qcontext={
                'team': team,
                'players_count': players_count,
                'players': players,
                'pager': pgr,
                'page_name': 'my_teams',
            }
        )

    @http.route(route=['/my/players', '/my/players/page/<int:page>'], type='http', auth='user', website=True)
    def view_players(self, page=0, **kw):
        """ Display the list of players that the portal user has access to """
        teams_domain = self._prepare_teams_domain()
        players_domain = self._prepare_players_domain(teams_domain)
        players_count = http.request.env['sports.patient'].search_count(players_domain)
        pgr = pager(url='/my/players', total=players_count, page=page, step=10, scope=5)
        players = http.request.env['sports.patient'].search(players_domain,
                                                            offset=pgr['offset'],
                                                            limit=players_count)
        return http.request.render(template='bemade_sports_clinic.portal_my_players',
                                   qcontext={
                                       'players_count': players_count,
                                       'players': players,
                                       'pager': pgr,
                                       'page_name': 'my_players',
                                   })

    @http.route(route=['/my/player'], type='http',
                auth='user', website=True)
    def view_player(self, player_id, team_id=None,**kw):
        """ Display the active injuries for a given player. """
        player_id = int(player_id)
        team_id = team_id and int(team_id)
        player = http.request.env['sports.patient'].browse(player_id)
        team = team_id and http.request.env['sports.team'].browse(team_id)
        if not player:
            raise UserError(_('This player could not be found.'))
            
        # Check if user is a treatment professional (portal version)
        user = http.request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Debug output
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"DEBUG - User: {user.name} (login: {user.login}) is treatment prof: {is_treatment_prof}")
        _logger.info(f"DEBUG - User groups: {', '.join([g.name for g in user.groups_id])}")
        _logger.info(f"DEBUG - XML ID check: {user.has_group('bemade_sports_clinic.group_portal_treatment_professional')}")
        
        # More detailed debugging
        _logger.info(f"DEBUG - Player ID: {player_id}, Team ID: {team_id}")
        if team_id:
            _logger.info(f"DEBUG - Team name: {team.name if team else 'Team not found'}")
            _logger.info(f"DEBUG - Team staff: {[(s.partner_id.name, s.role) for s in team.staff_ids]}")
        _logger.info(f"DEBUG - Player teams: {[t.name for t in player.team_ids]}")
        
        # Check team staff role
        staff_records = http.request.env['sports.team.staff'].sudo().search([('partner_id', '=', user.partner_id.id)])
        _logger.info(f"DEBUG - User's team staff roles: {[(s.team_id.name, s.role) for s in staff_records]}")
        _logger.info(f"DEBUG - User's partner ID: {user.partner_id.id}")
        
        # Check if user should have therapist role
        has_therapist_role = any(s.role in ['head_therapist', 'therapist'] for s in staff_records)
        _logger.info(f"DEBUG - User has therapist role: {has_therapist_role}")
        
        
        # Show all injuries to treatment professionals, but only active ones to coaches
        if is_treatment_prof:
            injuries = player.injury_ids
        else:
            injuries = player.injury_ids.filtered(lambda r: r.stage == 'active')
        
        # Create patient_info dictionary for protected fields (when user is a treatment professional)
        # No need for sudo() now that we have proper field-level access rights
        patient_info = {}
        if is_treatment_prof:
            # Include allergies and medical notes - direct access now that security is properly configured
            patient_info['allergies'] = player.allergies
            patient_info['team_info_notes'] = player.team_info_notes
        
        return http.request.render(
            template='bemade_sports_clinic.portal_my_player_injuries',
            qcontext={
                'player': player,
                'injuries': injuries,
                'team': team,
                'page_name': 'my_player',
                'is_treatment_prof': is_treatment_prof,
                'patient_info': patient_info,
            }
        )
