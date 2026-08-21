"""Task 1401 — a therapist's/coach's PERSONAL order of their teams.

One row per (user, team). It resolves the « Mon ordre » sort on the portal
``/my/teams`` page — the ``/odoo/`` app-icon placement analogue: purely
personal, never shared, never shown in the backend. Another staffer's list is
never affected by it (the record rule scopes every row to its own user).
"""
from odoo import api, fields, models

# Gap between consecutive ranks, same idea as the clinic worklist (#1398):
# leaves room for a later "insert between" without renumbering everything.
SEQUENCE_STEP = 10


class SportsTeamUserRank(models.Model):
    _name = "sports.team.user.rank"
    _description = "Personal Team Order (portal)"
    _order = "sequence, id"

    user_id = fields.Many2one(
        comodel_name="res.users",
        required=True,
        ondelete="cascade",
        index=True,
    )
    team_id = fields.Many2one(
        comodel_name="sports.team",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=0)

    _unique_user_team = models.Constraint(
        "UNIQUE(user_id, team_id)",
        "A team can only appear once in a user's personal order.",
    )

    # ------------------------------------------------------------------
    # the ONE ordering primitive — drag (full order) and up/down both land here
    # ------------------------------------------------------------------
    @api.model
    def _set_user_order(self, user, ordered_team_ids):
        """Make ``user``'s personal order follow ``ordered_team_ids``.

        Missing rank rows are created, existing ones renumbered; rows of the
        user for teams NOT in ``ordered_team_ids`` keep their relative order
        after the given ones (a team that dropped out of the caller's visible
        set is never silently dropped). Duplicates in the input are ignored
        past the first occurrence. The CALLER is responsible for restricting
        ``ordered_team_ids`` to teams the user may see — this method only
        orders, it does not authorize.
        """
        ranks = self.search([("user_id", "=", user.id)])
        by_team = {rank.team_id.id: rank for rank in ranks}
        seen = set()
        ordered = []
        for team_id in ordered_team_ids:
            if team_id in seen:
                continue
            seen.add(team_id)
            ordered.append(team_id)
        rest = [
            rank.team_id.id
            for rank in ranks.sorted(lambda r: (r.sequence, r.id))
            if rank.team_id.id not in seen
        ]
        to_create = []
        for index, team_id in enumerate(ordered + rest, start=1):
            position = index * SEQUENCE_STEP
            rank = by_team.get(team_id)
            if rank is None:
                to_create.append(
                    {"user_id": user.id, "team_id": team_id, "sequence": position}
                )
            elif rank.sequence != position:
                rank.sequence = position
        if to_create:
            self.create(to_create)
        return True

    @api.model
    def _resolve_user_order(self, user, teams, fallback_key=None):
        """Return ``teams`` (a recordset, already the user's VISIBLE set) as a
        list in the user's personal order: ranked teams first by rank, then the
        unranked ones in ``teams``'s own order (which the caller gives in
        "recent activity" order). Controller-resolved on purpose — team counts
        per user are tens, not thousands; at hundreds this would want a SQL
        join on the rank table instead.
        """
        ranks = self.search([("user_id", "=", user.id)])
        position = {
            rank.team_id.id: (rank.sequence, rank.id) for rank in ranks
        }
        ranked = [team for team in teams if team.id in position]
        ranked.sort(key=lambda team: position[team.id])
        unranked = [team for team in teams if team.id not in position]
        return ranked + unranked
