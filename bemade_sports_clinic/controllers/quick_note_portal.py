"""Portal surface for quick notes (task 1244) — `/my/notes`.

One page that is BOTH the capture form and the inbox: a therapist on the field
types a line, submits, and lands right back on a cleared, focused textarea so the
next note is type -> submit -> type. No note ever costs more than one POST.

Security shape, deliberately identical on every route here:
  1. group check (portal treatment professional),
  2. sudo(),
  3. `user_id` forced server-side to the authenticated user,
  4. ownership re-verified on EVERY write route — never inferred from the fact
     that the list query had filtered the record out.
"""
import logging
from datetime import timedelta

from odoo import _, fields, http
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal

from .access_control_mixin import AccessControlMixin

_logger = logging.getLogger(__name__)

# Window used to keep the optional event picker short enough to be usable on a
# phone: recent past plus the near future is what a therapist is capturing about.
EVENT_PICKER_PAST = 30
EVENT_PICKER_FUTURE = 60


class QuickNotePortal(CustomerPortal, AccessControlMixin):
    """Quick capture + inbox for a therapist's personal notes to self."""

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_quick_note_user():
        return request.env.user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional')

    def _check_quick_note_access(self):
        """Gate every quick-note route on the portal therapist group.

        Coaches (and any other portal role) are refused outright rather than
        shown an empty page — quick notes are a therapist tool.
        """
        if not self._is_quick_note_user():
            raise AccessError(_("Quick notes are available to treatment professionals only."))

    def _get_own_note(self, note_id):
        """Fetch a note and prove the caller owns it, or refuse.

        Ownership is re-checked here on purpose: the write routes take an id
        straight off the wire, so an id-guessing therapist must bounce off this
        and not off the record rule alone.
        """
        note = request.env['sports.quick.note'].sudo().with_context(
            active_test=False).browse(int(note_id))
        if not note.exists() or note.user_id != request.env.user:
            raise AccessError(_("You can only manage your own quick notes."))
        return note

    def _quick_note_pickers(self):
        """Optional link targets, scoped to what the therapist may see.

        Returned as recordsets for the template AND used server-side to validate
        whatever ids come back on the POST — a submitted id that is not in these
        sets is dropped, so the form cannot be used to link (and thereby render)
        a record outside the user's scope.
        """
        teams = self._get_accessible_teams()
        patients = request.env['sports.patient'].search(
            [('team_ids', 'in', teams.ids)])
        injuries = request.env['sports.patient.injury'].search([
            ('patient_id', 'in', patients.ids),
            ('stage', '!=', 'resolved'),
        ])
        now = fields.Datetime.now()
        events = request.env['sports.event'].search([
            ('team_ids', 'in', teams.ids),
            ('date_start', '>=', now - timedelta(days=EVENT_PICKER_PAST)),
            ('date_start', '<=', now + timedelta(days=EVENT_PICKER_FUTURE)),
        ], order='date_start desc')
        return {
            'teams': teams,
            'patients': patients,
            'injuries': injuries,
            'events': events,
        }

    @staticmethod
    def _clean_link_vals(post, pickers):
        """Turn posted link ids into write values, dropping anything out of scope."""
        allowed = {
            'team_id': pickers['teams'].ids,
            'patient_id': pickers['patients'].ids,
            'injury_id': pickers['injuries'].ids,
            'event_id': pickers['events'].ids,
        }
        vals = {}
        for fname, allowed_ids in allowed.items():
            raw = (post.get(fname) or '').strip()
            if not raw:
                vals[fname] = False
                continue
            try:
                candidate = int(raw)
            except ValueError:
                vals[fname] = False
                continue
            vals[fname] = candidate if candidate in allowed_ids else False
        return vals

    # ------------------------------------------------------------------
    # portal home counter
    # ------------------------------------------------------------------
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if self._is_quick_note_user():
            values['quick_notes_count'] = request.env['sports.quick.note'].search_count([
                ('user_id', '=', request.env.user.id),
                ('active', '=', True),
            ])
        return values

    # ------------------------------------------------------------------
    # routes
    # ------------------------------------------------------------------
    @http.route(['/my/notes'], type='http', auth='user', website=True)
    def portal_my_quick_notes(self, show_archived=None, **kw):
        """Quick-add on top, the therapist's own active notes newest-first below."""
        self._check_quick_note_access()
        Note = request.env['sports.quick.note'].sudo()
        # Always scope by owner in the query too: a clinic administrator holds a
        # read-all record rule, and their own /my/notes must still be their own.
        own = [('user_id', '=', request.env.user.id)]
        notes = Note.search(own + [('active', '=', True)])
        archived = Note.with_context(active_test=False).search(
            own + [('active', '=', False)]) if show_archived else Note.browse()

        values = self._quick_note_pickers()
        values.update({
            'notes': notes,
            'archived_notes': archived,
            'show_archived': bool(show_archived),
            'archived_count': Note.with_context(active_test=False).search_count(
                own + [('active', '=', False)]),
            'page_name': 'quick_notes',
            'error': kw.get('error'),
            'success': kw.get('success'),
        })
        return request.render('bemade_sports_clinic.portal_my_quick_notes', values)

    @http.route(['/my/notes/add'], type='http', auth='user', website=True,
                methods=['POST'])
    def portal_quick_note_add(self, **post):
        """Capture one note. Nothing but the text is required."""
        self._check_quick_note_access()
        note_text = post.get('note') or ''
        if not note_text.strip():
            return request.redirect('/my/notes?error=empty_note#quick-add')

        vals = self._clean_link_vals(post, self._quick_note_pickers())
        vals.update({
            'note': note_text,
            # Never trust a posted owner.
            'user_id': request.env.user.id,
        })
        request.env['sports.quick.note'].sudo().create(vals)
        # Back to a cleared, focused textarea so the next note is immediate.
        return request.redirect('/my/notes?success=note_added#quick-add')

    @http.route(['/my/notes/<int:note_id>/update'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_quick_note_update(self, note_id, **post):
        """Edit a captured note's text and its optional links, later, from the inbox."""
        self._check_quick_note_access()
        note = self._get_own_note(note_id)
        note_text = post.get('note') or ''
        if not note_text.strip():
            return request.redirect(f'/my/notes?error=empty_note#note-{note.id}')
        vals = self._clean_link_vals(post, self._quick_note_pickers())
        vals['note'] = note_text
        note.write(vals)
        return request.redirect(f'/my/notes?success=note_updated#note-{note.id}')

    @http.route(['/my/notes/<int:note_id>/archive'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_quick_note_archive(self, note_id, **post):
        """Dismiss / mark handled — archiving IS the 'done' concept here."""
        self._check_quick_note_access()
        self._get_own_note(note_id).write({'active': False})
        return request.redirect('/my/notes?success=note_archived#quick-add')

    @http.route(['/my/notes/<int:note_id>/restore'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_quick_note_restore(self, note_id, **post):
        """Undo a dismissal — a mis-tapped Dismiss must not lose the thought."""
        self._check_quick_note_access()
        self._get_own_note(note_id).write({'active': True})
        return request.redirect('/my/notes?show_archived=1&success=note_restored')

    @http.route(['/my/notes/<int:note_id>/delete'], type='http', auth='user',
                website=True, methods=['POST'])
    def portal_quick_note_delete(self, note_id, **post):
        """Purge. Retention here is by hand on purpose: notes are the owner's to
        delete when done, and the system only ever nudges (no auto-purge)."""
        self._check_quick_note_access()
        self._get_own_note(note_id).unlink()
        return request.redirect('/my/notes?success=note_deleted')
