"""Task 1628 — « Compléter la fiche du joueur » To-Dos.

A daily cron looks at the players created since the cut-off parameter
(``INCOMPLETE_TODO_SINCE_PARAM``, set to the upgrade time by the 19.0.1.94.0
post-migrate: no backfill) and older than the grace period. A player whose
file is still incomplete gets ONE To-Do listing what is missing; the To-Do
follows the file on every run and closes itself (marked done) once the file
is complete. A To-Do dismissed by hand (marked done or cancelled) while items
are still missing is never raised again for that player.

Checklist (``_sc_incomplete_items``):

* the name (required at ORM level — kept for completeness);
* the date of birth;
* an emergency contact with a phone number (any ``contact_ids`` row with a
  ``mobile``);
* for a player aged 14 or more — or whose date of birth is missing — the
  player's own email and phone, each listed separately.

Assignee (``_sc_incomplete_todo_assignee``), so the To-Do lands with someone
who can both see the player in the portal app and edit these fields:

1. the creator, when active, not the system user, holding
   treatment-professional rights, and either a clinic admin or staff on one
   of the player's teams;
2. otherwise the first head therapist, then therapist, of the player's teams
   (team order, then staff order);
3. otherwise the first active clinic admin (by id).

Players created by the system / root user (script imports) are skipped.
"""
from datetime import timedelta

from markupsafe import Markup, escape

from odoo import SUPERUSER_ID, api, fields, models

INCOMPLETE_TODO_SINCE_PARAM = 'bemade_sports_clinic.incomplete_todo_since'
INCOMPLETE_TODO_GRACE_HOURS = 48
# The personal email / phone are asked for from this age on (or when the date
# of birth is unknown).
INCOMPLETE_TODO_PERSONAL_AGE = 14
INCOMPLETE_TODO_ITEMS = (
    'first_name', 'last_name', 'date_of_birth', 'emergency_contact', 'email', 'phone',
)
TP_GROUPS = (
    'bemade_sports_clinic.group_sports_clinic_treatment_professional',
    'bemade_sports_clinic.group_portal_treatment_professional',
)
CLINIC_ADMIN_GROUP = 'bemade_sports_clinic.group_sports_clinic_admin'
THERAPIST_ROLES = ('head_therapist', 'therapist')


class Patient(models.Model):
    _inherit = 'sports.patient'

    incomplete_todo_raised = fields.Boolean(
        string='Incomplete-file To-Do raised',
        copy=False,
        groups='base.group_system',
        help="Technical (task 1628): an « incomplete file » To-Do was raised "
        "for this player once. A To-Do marked done or cancelled is never "
        "raised again.",
    )

    # ------------------------------------------------------------------
    # Checklist
    # ------------------------------------------------------------------
    def _sc_incomplete_items(self):
        """Keys of ``INCOMPLETE_TODO_ITEMS`` missing on this player (in that
        order). Reads in sudo: the fields are group-restricted."""
        self.ensure_one()
        player = self.sudo()
        missing = []
        if not (player.first_name or '').strip():
            missing.append('first_name')
        if not (player.last_name or '').strip():
            missing.append('last_name')
        if not player.date_of_birth:
            missing.append('date_of_birth')
        if not any((c.mobile or '').strip() for c in player.contact_ids):
            missing.append('emergency_contact')
        if not player.date_of_birth or player.age >= INCOMPLETE_TODO_PERSONAL_AGE:
            if not (player.email or '').strip():
                missing.append('email')
            if not (player.phone or '').strip():
                missing.append('phone')
        return missing

    def _sc_incomplete_labels(self):
        """Label of each checklist key, in the env's language."""
        _ = self.env._
        return {
            'first_name': _("First name"),
            'last_name': _("Last name"),
            'date_of_birth': _("Date of birth"),
            'emergency_contact': _("Emergency contact with a phone number"),
            'email': _("Player's email"),
            'phone': _("Player's phone"),
        }

    def _sc_incomplete_todo_texts(self, missing, lang):
        """(summary, note) of the To-Do, rendered in ``lang``."""
        player = self.with_context(lang=lang)
        labels = player._sc_incomplete_labels()
        summary = player.env._("Complete the player's file")
        intro = player.env._("The following information is missing from this player's file:")
        items = Markup('').join(
            Markup('<li>%s</li>') % escape(labels[key]) for key in missing)
        note = Markup('<p>%s</p><ul>%s</ul>') % (escape(intro), items)
        return summary, note

    # ------------------------------------------------------------------
    # Assignee
    # ------------------------------------------------------------------
    @api.model
    def _sc_is_assignable(self, user):
        return bool(user) and user.active and user.id != SUPERUSER_ID

    @api.model
    def _sc_has_tp_rights(self, user):
        return any(user.has_group(group) for group in TP_GROUPS)

    @api.model
    def _sc_first_clinic_admin(self):
        admins = self.env.ref(CLINIC_ADMIN_GROUP).sudo().all_user_ids.filtered(
            lambda u: self._sc_is_assignable(u) and not u.share)
        return admins.sorted('id')[:1]

    def _sc_incomplete_todo_assignee(self):
        """See the module docstring. Empty when nobody qualifies."""
        self.ensure_one()
        player = self.sudo()
        teams = player.team_ids
        creator = player.create_uid
        if self._sc_is_assignable(creator) and self._sc_has_tp_rights(creator):
            if creator.has_group(CLINIC_ADMIN_GROUP) or (
                    creator.partner_id in teams.staff_ids.partner_id):
                return creator
        for team in teams:
            staff = team.staff_ids.filtered(lambda s: s.role in THERAPIST_ROLES).sorted(
                lambda s: (THERAPIST_ROLES.index(s.role), s.sequence, s.id))
            for row in staff:
                users = row.user_ids.filtered(self._sc_is_assignable)
                if users:
                    return users.sorted('id')[:1]
        return self._sc_first_clinic_admin()

    # ------------------------------------------------------------------
    # Cron
    # ------------------------------------------------------------------
    @api.model
    def _cron_incomplete_player_todos(self):
        ICP = self.env['ir.config_parameter'].sudo()
        now = fields.Datetime.now()
        try:
            since = fields.Datetime.to_datetime(ICP.get_param(INCOMPLETE_TODO_SINCE_PARAM))
        except ValueError:
            since = False
        if not since:
            # Fresh install (no post-migrate): start sweeping from now on.
            ICP.set_param(INCOMPLETE_TODO_SINCE_PARAM, fields.Datetime.to_string(now))
            return True

        players = self.sudo().search([
            ('create_date', '>=', since),
            ('create_date', '<=', now - timedelta(hours=INCOMPLETE_TODO_GRACE_HOURS)),
        ])
        if not players:
            return True

        Activity = self.env['mail.activity'].sudo()
        open_todos = Activity.search([
            ('res_model', '=', self._name),
            ('res_id', 'in', players.ids),
            ('patient_incomplete_todo', '=', True),
        ]).grouped('res_id')
        todo_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        model_id = self.env['ir.model']._get(self._name).id

        for player in players:
            missing = player._sc_incomplete_items()
            todo = open_todos.get(player.id, Activity)[:1]
            if todo:
                if not missing:
                    todo.action_done()
                    continue
                vals = {}
                assignee = todo.user_id
                if not self._sc_is_assignable(assignee):
                    assignee = player._sc_incomplete_todo_assignee()
                    if assignee:
                        vals['user_id'] = assignee.id
                summary, note = player._sc_incomplete_todo_texts(
                    missing, assignee.lang or self.env.lang)
                if todo.summary != summary:
                    vals['summary'] = summary
                if str(todo.note or '') != str(note):
                    vals['note'] = note
                if vals:
                    todo.write(vals)
                continue
            if not missing or player.incomplete_todo_raised:
                continue
            if player.create_uid.id == SUPERUSER_ID or not player.create_uid:
                continue
            assignee = player._sc_incomplete_todo_assignee()
            if not assignee:
                continue
            summary, note = player._sc_incomplete_todo_texts(
                missing, assignee.lang or self.env.lang)
            Activity.with_context(lang=assignee.lang or self.env.lang).create({
                'res_model_id': model_id,
                'res_id': player.id,
                'patient_incomplete_todo': True,
                'user_id': assignee.id,
                'activity_type_id': todo_type.id if todo_type else False,
                'summary': summary,
                'note': note,
                'date_deadline': fields.Date.context_today(self),
                'automated': True,
            })
            player.with_context(tracking_disable=True).incomplete_todo_raised = True
        return True
