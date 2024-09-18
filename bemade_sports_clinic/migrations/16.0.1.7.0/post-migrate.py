""" Patient access revised to make the team staff relationship central to
access. Everything is calculated from there. Inverse functions deal with
sports.team.staff records instead of having a separate table for storing
access rights."""
def migrate(cr, version):
    cr.execute("DROP TABLE sports_team_res_users_rel")