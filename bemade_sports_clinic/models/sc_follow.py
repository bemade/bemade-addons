"""Task 1624, review round 1 (owner 2026-10-29) — « Suivre » a player.

A personal follow list: ``res.users.sc_followed_patient_ids`` (system group
only, see there). Everything goes through the two members below, always for
``self.env.user``:

* ``_sc_follow(follow)`` — follow / unfollow players the user can READ (the
  record rules of sports.patient apply: an unreadable player raises
  AccessError, nothing is stored);
* ``sc_followed_by_me`` — does the CURRENT user follow this player? Never
  another user's answer: a user's follows are private to them.

The dashboard's « Joueurs que je suis » widget reads them with
``sc.dashboard._sc_data_followed``.
"""
from odoo import api, fields, models

from . import sc_app_roles


class SportsPatientFollow(models.Model):
    _inherit = 'sports.patient'

    sc_followed_by_me = fields.Boolean(
        string="Followed by Me",
        compute='_compute_sc_followed_by_me',
        help="The current user follows this player (their own dashboard).",
    )

    @api.depends_context('uid')
    def _compute_sc_followed_by_me(self):
        followed = set(self.env.user.sudo().sc_followed_patient_ids.ids)
        for patient in self:
            patient.sc_followed_by_me = patient.id in followed

    def _sc_follow_allowed(self):
        """May the current user follow players at all (the staff roles)?"""
        user = self.env.user
        return sc_app_roles.can('patient.follow', user._sc_app_roles(),
                                is_system=user.has_group('base.group_system'))

    def _sc_follow_state(self):
        """For the toggle: None (no toggle for this user), else whether the
        current user follows this player."""
        self.ensure_one()
        if not self._sc_follow_allowed():
            return None
        return self.sc_followed_by_me

    def _sc_follow(self, follow=True):
        """Follow (``follow``) or unfollow these players for the current
        user. Following needs read access to each player (AccessError
        otherwise); unfollowing is always allowed (a player whose access
        was lost can still be dropped)."""
        if follow:
            self.check_access('read')
        user = self.env.user.sudo()
        if follow:
            user.sc_followed_patient_ids = [fields.Command.link(p.id) for p in self]
        else:
            user.sc_followed_patient_ids = [fields.Command.unlink(p.id) for p in self]
        self.invalidate_recordset(['sc_followed_by_me'])
        return True
