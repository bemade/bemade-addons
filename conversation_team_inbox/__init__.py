from . import models


def post_init_hook(env):
    """Give every team that predates this module its alias and its team
    transport, so installing on a populated database needs no manual step."""
    teams = env["mail.conversation.team"].with_context(active_test=False).search([])
    for team in teams.filtered(lambda t: not t.alias_id):
        team.alias_id = (
            env["mail.alias"].sudo().create(team._alias_get_creation_values())
        )
    teams._sync_team_transport()
