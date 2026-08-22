import logging
import base64
import io
import re
import unicodedata
from odoo import http, fields, _
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from .access_control_mixin import AccessControlMixin
from datetime import datetime

_logger = logging.getLogger(__name__)


def _nav_ctx_qs(post, clinic, team_key='team_id'):
    """Navigation-context tail (``&team_id=…&clinic_id=…``) to re-append to a
    redirect built from scratch, so a round-trip through a POST handler
    keeps the team AND clinic (task 1410) the form was opened from.
    ``team_id`` is taken verbatim from the form (it is only ever used for
    navigation and re-validated by the page it lands on); ``clinic`` is the
    already-validated event from ``_clinic_context``."""
    tail = ''
    raw_team = post.get(team_key)
    try:
        if raw_team:
            tail += f'&team_id={int(raw_team)}'
    except (TypeError, ValueError):
        pass
    if clinic:
        tail += f'&clinic_id={clinic.id}'
    return tail


class PatientInjuryPortal(CustomerPortal, AccessControlMixin):
    """Controller for all injury reporting functionality in the portal"""
    
    # Access control methods now inherited from AccessControlMixin
    
    @http.route(['/my/patient/injury/new'], type='http', auth='user', website=True)
    def create_injury_form(self, patient_id=None, **post):
        """Show form to create a new injury report"""
        if not patient_id:
            return request.redirect('/my/players')
            
        patient = self._check_access_to_patient(patient_id)
        values = self._create_injury_form_values(patient, post)
        return request.render('bemade_sports_clinic.portal_create_injury', values)

    def _create_injury_form_values(self, patient, post):
        """The create form's qcontext — shared by the page and, with the
        task-1412 overrides applied on top, by the clinic modal fragment."""
        patient_id = patient.id
        # Resolve team context. Read the patient's teams via sudo so
        # multi-team players still render the "which team is this injury
        # for?" picker even when one of the teams is outside the user's
        # tightened TP/coach scope.
        patient_teams = patient.sudo().team_ids
        # Accept team context from both kwargs and request.params (GET)
        team_id_param = post.get('team_id') or request.params.get('team_id')
        selected_team_id = None
        team_context_id = None
        if team_id_param:
            try:
                team_id_int = int(team_id_param)
            except Exception:
                team_id_int = None
            if team_id_int and team_id_int in patient_teams.ids:
                # Explicit, validated team context coming from navigation
                selected_team_id = team_id_int
                team_context_id = team_id_int
        # Single-team inference for form convenience only (no breadcrumb context)
        if not selected_team_id and len(patient_teams) == 1:
            selected_team_id = patient_teams[0].id
        require_team_selection = len(patient_teams) > 1 and not selected_team_id
        team = None
        if team_context_id:
            # sudo so an out-of-scope team still renders by name in the form
            team = request.env['sports.team'].sudo().browse(team_context_id)
        
        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(post)

        # Compute default return_url based on explicit team navigation context only
        return_url = self._local_return_url(
            post.get('return_url') or request.params.get('return_url'), None)
        if not return_url:
            if team_context_id:
                return_url = f'/my/player?player_id={patient_id}&team_id={team_context_id}'
            else:
                return_url = f'/my/player?player_id={patient_id}'
            return_url = self._with_clinic(return_url, clinic_event)

        # Check if user is a treatment professional
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        # Get treatment professionals for the multi-select field (if treatment professional)
        treatment_professionals = []
        parental_consent_options = None
        if is_treatment_prof:
            # Include both portal and internal treatment professionals
            portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
            internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            # all_group_ids (effective membership) so clinic admins/doctors, who
            # hold the TP group only by implication, are not excluded. sudo: the
            # all_group_ids search reads res.groups, which portal users cannot
            # access — identity-level list, so sudo is safe.
            treatment_professionals = request.env['res.users'].sudo().search([
                ('all_group_ids', 'in', [portal_tp_group.id, internal_tp_group.id])
            ])
            parental_consent_options = request.env['sports.patient.injury']._fields['parental_consent'].selection
        
        values = {
            'patient': patient,
            'return_url': return_url,
            'page_name': 'report_injury',
            'is_treatment_prof': is_treatment_prof,  # Pass flag to template for conditional display
            'treatment_professionals': treatment_professionals,
            'parental_consent_options': parental_consent_options,
            'patient_teams': patient_teams,
            'selected_team_id': selected_team_id,
            'require_team_selection': require_team_selection,
            'team': team,
            'team_context_id': team_context_id,
            'clinic_event': clinic_event,
            'error': post.get('error'),
        }
        return values

    @http.route(['/my/patient/injury/new/fragment'], type='http', auth='user',
                website=True, methods=['GET'])
    def create_injury_form_fragment(self, patient_id=None, **kw):
        """Task 1412 — the QUICK-ADD injury form alone (no page chrome), for
        the clinic dossier's « Add injury » modal.

        Same access checks as /my/patient/injury/new (patient access) PLUS the
        clinic gate: the caller must be a clinic user and ``clinic_id`` must
        resolve to an accessible clinic — 403 otherwise. Pre-fills: the team
        (the clinic's single team when it is one of the patient's, else the
        patient's only team, else a select), the current user as the only
        treatment professional (hidden), stage Active, and a return_url back
        to this clinic with the patient selected. Never cached.
        """
        try:
            if not patient_id:
                raise MissingError(_('Patient not found.'))
            patient = self._check_access_to_patient(patient_id)
            clinic_event = self._require_clinic_for_fragment(kw)
        except UserError as error:
            return self._forbidden(error)
        values = self._create_injury_form_values(patient, kw)
        patient_teams = values['patient_teams']
        # Team block (task 1412, kept minimal for #1240): ONE hidden input when
        # it is unambiguous, else the regular select. The clinic's single team
        # wins when it is one of the patient's teams.
        quick_team_id = None
        if len(clinic_event.team_ids) == 1 and clinic_event.team_ids.id in patient_teams.ids:
            quick_team_id = clinic_event.team_ids.id
        elif len(patient_teams) == 1:
            quick_team_id = patient_teams.id
        stage_selection = []
        if values['is_treatment_prof']:
            stage_selection = request.env['sports.patient.injury']._fields['stage']._description_selection(request.env)
        values.update({
            'modal': True,
            'quick': True,
            'clinic_event': clinic_event,
            'return_url': self._clinic_return_url(clinic_event, patient.id, anchor='clinic-injuries'),
            'quick_team_id': quick_team_id,
            'selected_team_id': quick_team_id or values['selected_team_id'],
            'require_team_selection': not quick_team_id and len(patient_teams) > 1,
            # navigation tail for an error round-trip back to the full page
            'team_context_id': clinic_event.team_ids.id if len(clinic_event.team_ids) == 1 else None,
            'quick_tp_id': request.env.user.id,
            'stages': stage_selection,
            'quick_stage': 'active',
        })
        return self._render_fragment('bemade_sports_clinic.portal_injury_create_form_body', values)

    def _require_clinic_for_fragment(self, params):
        """The clinic a fragment is opened from — clinic users only, and the
        clinic_id must resolve (task 1412); raises AccessError otherwise so
        the route answers 403 exactly like /my/clinic/<id> would."""
        user = request.env.user
        is_clinic_user = (
            user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
            or user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            or user.has_group('base.group_system'))
        if not is_clinic_user:
            raise AccessError(_("Clinics are available to treatment professionals only."))
        clinic_event = self._clinic_context(params)
        if not clinic_event:
            raise AccessError(_("This form can only be opened from a clinic."))
        return clinic_event

    @staticmethod
    def _render_fragment(template, values):
        """Render ``template`` alone (no portal layout), never cached — the
        same way the clinic worklist fragment (#1397) is served."""
        values['request'] = request
        html = request.env['ir.ui.view']._render_template(template, values)
        return request.make_response(html, headers=[
            ('Content-Type', 'text/html; charset=utf-8'),
            ('Cache-Control', 'no-store'),
        ])
    
    @http.route(['/my/patient/injury/create'], type='http', auth='user', website=True, methods=['POST'])
    def create_injury_submit(self, **post):
        """Process the form submission to create a new injury"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        patient = self._check_access_to_patient(patient_id)
        clinic_event = self._clinic_context(post)
        # Context tail for the error round-trips back to the form (task 1410):
        # the form's team_context_id (NOT the team picked in the form) + clinic.
        form_ctx_qs = _nav_ctx_qs(post, clinic_event, team_key='team_context_id')
            
        # Resolve team from submission or context. sudo so that
        # multi-team players whose teams the user can't all read still
        # validate the submitted team properly.
        patient_teams = patient.sudo().team_ids
        submitted_team = post.get('team_id')
        team_id = None
        if submitted_team:
            try:
                submitted_team_int = int(submitted_team)
            except Exception:
                submitted_team_int = None
            if submitted_team_int and submitted_team_int in patient_teams.ids:
                team_id = submitted_team_int
            else:
                # Invalid team submitted; re-render form with error
                return request.redirect(f"/my/patient/injury/new?patient_id={patient.id}{form_ctx_qs}&error=invalid_team")
        else:
            if len(patient_teams) == 1:
                team_id = patient_teams[0].id
            elif len(patient_teams) > 1:
                # Team selection required when multiple teams and no selection provided
                return request.redirect(f"/my/patient/injury/new?patient_id={patient.id}{form_ctx_qs}&error=team_required")
            
        # Check if the current user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Prepare values for injury creation
        vals = {
            'patient_id': patient.id,
            'diagnosis': post.get('diagnosis', ''),
            'external_notes': post.get('external_notes', ''),
        }
        
        # Handle injury date and injury_date_na checkbox
        if post.get('injury_date_na'):
            vals['injury_date_na'] = True
            vals['injury_date'] = False  # Clear injury_date if N/A is checked
        elif post.get('injury_date'):
            vals['injury_date'] = post.get('injury_date')
            vals['injury_date_na'] = False
        
        # Add team_id if resolved
        if team_id:
            vals['team_id'] = int(team_id)
        
        # Handle optional fields
        if post.get('parental_consent'):
            vals['parental_consent'] = post.get('parental_consent')
        
        if post.get('predicted_resolution_date'):
            vals['predicted_resolution_date'] = post.get('predicted_resolution_date')
            
        # Handle internal notes for treatment professionals
        if is_treatment_prof and post.get('internal_notes'):
            vals['internal_notes'] = post.get('internal_notes')

        # Hidden-from-coaches flag (TPs only — checkbox)
        if is_treatment_prof:
            vals['hidden_from_coaches'] = bool(post.get('hidden_from_coaches'))

        # Stage (task 1412: the clinic quick-add form posts one; TP-only, as
        # on the edit form). Absent ⇒ the model's own default per creator role.
        stage_values = dict(request.env['sports.patient.injury']._fields['stage'].selection)
        requested_stage = post.get('stage') if is_treatment_prof else None
        if requested_stage and requested_stage not in stage_values:
            requested_stage = None
            
        # Create the injury record - portal users now have create permission
        # Determine role flags to choose safe context
        is_internal_user = request.env.user.has_group('base.group_user')
        is_tp_internal = request.env.user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_tp_portal = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        suppress_notifications = not (is_internal_user or is_tp_internal or is_tp_portal)

        env_injury = request.env['sports.patient.injury']
        if suppress_notifications:
            env_injury = env_injury.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True)
        injury = env_injury.create(vals)
        if requested_stage and injury.stage != requested_stage:
            # After create: the model's create hook sets the role default
            # (active for TPs) and would override a value passed in vals.
            injury.sudo().with_context(mail_notrack=True).write({'stage': requested_stage})
        
        # Determine role for assignment behavior
        # Use request.env.user.has_group() directly to avoid security violations
        is_portal_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user

        # Assignment rules:
        # - If any therapists were explicitly selected in the form, assign exactly those and do not auto-assign others.
        # - If none were selected, auto-assign team therapists (if determinable) and do not auto-assign the creator by default.

        # Read explicit selections (checkbox-based multi-select)
        selected_tp_ids = []
        if is_treatment_prof:
            selected_tp_ids = request.httprequest.form.getlist('treatment_professional_ids[]') or []
            # Normalize to ints and remove empties
            selected_tp_ids = [int(tp_id) for tp_id in selected_tp_ids if tp_id]

        if selected_tp_ids:
            # Respect explicit selection only.
            # sudo: Odoo 19 validates m2m target IDs by reading them; portal
            # users lack read on res.users. The IDs are server-side trusted
            # (form submitted them, controller is the gatekeeper).
            if suppress_notifications:
                injury.sudo().with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True).write({'treatment_professional_ids': [(6, 0, selected_tp_ids)]})
            else:
                injury.sudo().write({'treatment_professional_ids': [(6, 0, selected_tp_ids)]})
        else:
            # No explicit selection: perform team-based auto-assignment (if a single team context exists)
            if team_id:
                selected_team_id = int(team_id)
                # Find therapists (head and regular) specifically for this team
                team_staff = request.env['sports.team.staff'].sudo().search([
                    ('team_id', '=', selected_team_id),
                    ('role', 'in', ['head_therapist', 'therapist'])
                ])

                # Collect user IDs from team staff (prefer direct user_ids relation, fallback to partner mapping)
                team_tp_user_ids = set()
                for staff in team_staff:
                    if staff.user_ids:
                        for u in staff.user_ids:
                            team_tp_user_ids.add(u.id)
                    else:
                        users = request.env['res.users'].sudo().search([('partner_id', '=', staff.partner_id.id)])
                        for u in users:
                            team_tp_user_ids.add(u.id)

                if user.id in team_tp_user_ids and (user.id not in (selected_tp_ids or [])):
                    # Do not auto-assign the creating user unless explicitly selected
                    team_tp_user_ids.discard(user.id)

                if not team_tp_user_ids:
                    _logger.warning("No valid therapists found to assign to the injury for team %s", selected_team_id)

                if team_tp_user_ids:
                    # sudo: see comment above — m2m target read in 19.
                    if suppress_notifications:
                        injury.sudo().with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True).write({'treatment_professional_ids': [(6, 0, list(team_tp_user_ids))]})
                    else:
                        injury.sudo().write({'treatment_professional_ids': [(6, 0, list(team_tp_user_ids))]})
            else:
                _logger.info(
                    "Skipping team-based therapist auto-assignment: patient %s has %s teams",
                    patient.id,
                    len(patient.team_ids),
                )
            
        # Handle treatment note creation if provided by treatment professional
        if is_treatment_prof and post.get('treatment_note'):
            treatment_note_text = post.get('treatment_note').strip()
            if treatment_note_text:
                try:
                    # Create treatment note using the controller helper to ensure correct permissions and linkage
                    self._add_treatment_note(injury.patient_id, treatment_note_text, injury)
                    _logger.info(f"Treatment note added to injury {injury.id} by user {request.env.user.id}")
                except Exception as e:
                    _logger.error(f"Failed to create treatment note for injury {injury.id}: {str(e)}")
        
        # Trigger recomputation of patient status based on the injury
        patient._compute_is_injured()
        patient._compute_stage()
        
        # Use explicit navigation context (team_context_id) for redirect, not inferred team assignment
        team_context_id = post.get('team_context_id')
        try:
            team_context_id_int = int(team_context_id) if team_context_id else None
        except Exception:
            team_context_id_int = None

        if team_context_id_int and team_context_id_int in patient_teams.ids:
            return_url = f'/my/player?player_id={patient_id}&team_id={team_context_id_int}'
        else:
            return_url = f'/my/player?player_id={patient_id}'
        # « Back to player » keeps the clinic context (task 1410).
        return_url = self._with_clinic(return_url, clinic_event)

        # Task 1412: created FROM a clinic (the form's return_url is a clinic
        # page) ⇒ go straight back there, same patient, the new card in view.
        # Every other caller keeps the « created » page below.
        posted_return_url = self._local_return_url(post.get('return_url'), None)
        if self._is_clinic_page_url(posted_return_url):
            base = posted_return_url.partition('#')[0]
            return request.redirect(self._url_with_query(
                base, 'success=injury_created') + '#clinic-injury-%s' % injury.id)
        values = {
            'return_url': return_url,
        }
        
        return request.render('bemade_sports_clinic.portal_injury_created', values)
        
    # _check_access_to_injury method now inherited from AccessControlMixin

    def _sanitize_filename(self, name):
        """Return an ASCII-safe filename for HTTP headers/storage.
        - Normalize unicode
        - Remove path separators
        - Strip non-ASCII characters
        - Replace illegal chars with underscore
        - Truncate to a reasonable length
        """
        try:
            if not name:
                return 'document'
            # Normalize unicode then drop accents
            norm = unicodedata.normalize('NFKD', str(name))
            norm = norm.replace('/', '-').replace('\\', '-')
            # Encode to ASCII, ignore non-ASCII
            ascii_name = norm.encode('ascii', 'ignore').decode('ascii')
            # Allow alnum, space, dot, dash, underscore only
            ascii_name = re.sub(r'[^A-Za-z0-9._ -]', '_', ascii_name)
            # Collapse whitespace and trim
            ascii_name = re.sub(r'\s+', ' ', ascii_name).strip()
            if not ascii_name:
                ascii_name = 'document'
            # Limit length
            return ascii_name[:150]
        except Exception:
            return 'document'
        
    @http.route(['/my/injury/edit'], type='http', auth='user', website=True)
    def edit_injury_form(self, injury_id=None, team_id=None, **post):
        """Show form to edit an existing injury"""
        if not injury_id:
            return request.redirect('/my/players')
            
        injury = self._check_access_to_injury(injury_id)
        values = self._edit_injury_form_values(injury, team_id, post)
        return request.render('bemade_sports_clinic.portal_edit_injury', values)

    def _edit_injury_form_values(self, injury, team_id, post):
        """The edit form's qcontext — shared by the page and, with the
        task-1412 overrides applied on top, by the clinic modal fragment."""
        # Determine return URL. If an explicit return_url is provided, respect it;
        # otherwise, build a player URL, optionally including validated team context
        # so that saving/cancelling from a team-aware player page keeps team_id.
        return_url = self._local_return_url(post.get('return_url'), None)
        team = None
        team_context_id = None
        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(post)

        if not return_url:
            team_param = team_id or request.params.get('team_id')
            if team_param:
                try:
                    # Best-effort team validation for navigation context
                    team_rec = self._check_team_access(team_param, check_staff=True)
                    if team_rec:
                        team = team_rec
                        team_context_id = team_rec.id
                except UserError:
                    team = None
                    team_context_id = None

            if team_context_id:
                return_url = f'/my/player?player_id={injury.patient_id.id}&team_id={team_context_id}'
            else:
                return_url = f'/my/player?player_id={injury.patient_id.id}'
            return_url = self._with_clinic(return_url, clinic_event)

        # Navigation-context tail for the links this page builds (documents,
        # note history): team + clinic, so they come back here the same way.
        ctx_qs = ''
        if team_context_id:
            ctx_qs += f'&team_id={team_context_id}'
        if clinic_event:
            ctx_qs += f'&clinic_id={clinic_event.id}'
        
        # Get possible injury stages - treatment professionals can change stage
        stages = []
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        if is_treatment_prof:
            stage_selection = request.env['sports.patient.injury']._fields['stage'].selection
            stages = [(k, v) for k, v in stage_selection]
        
        # Get treatment professionals for the multi-select field (both portal and internal).
        # all_group_ids (effective membership) so clinic admins/doctors, who hold the
        # TP group only by implication, are not excluded. sudo: this route
        # (edit_injury_form) is reachable by any portal user and the all_group_ids
        # search reads res.groups (no portal ACL) — identity-level list, sudo safe.
        portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        treatment_professionals = request.env['res.users'].sudo().search([
            ('all_group_ids', 'in', [portal_tp_group.id, internal_tp_group.id])
        ])
        
        # Get parental consent options if treatment professional
        parental_consent_options = None
        if is_treatment_prof:
            parental_consent_options = request.env['sports.patient.injury']._fields['parental_consent'].selection
            
        values = {
            'injury': injury,
            # Pre-resolved under sudo: treatment_professional_ids is an m2m to
            # res.users; reading it (even .ids) non-sudo in the template drops
            # users the portal viewer can't read, so assigned cross-team TPs
            # disappeared from the pre-checked boxes. Compare by id in the view.
            'selected_tp_ids': injury.sudo().treatment_professional_ids.ids,
            'stages': stages,
            'treatment_professionals': treatment_professionals,
            'parental_consent_options': parental_consent_options,
            'return_url': return_url,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'edit_injury',
            'error': post.get('error'),
            'success': post.get('success'),
            'team': team,
            'team_context_id': team_context_id,
            'clinic_event': clinic_event,
            'ctx_qs': ctx_qs,
        }
        return values

    @http.route(['/my/injury/<int:injury_id>/form/fragment'], type='http', auth='user',
                website=True, methods=['GET'])
    def edit_injury_form_fragment(self, injury_id, **kw):
        """Task 1412 — the full edit form alone (no page chrome), for the
        clinic dossier's « open injury » modal.

        Same access checks as /my/injury/edit (injury access) PLUS the clinic
        gate (clinic user + a resolvable ``clinic_id``) — 403 otherwise. The
        form's return_url is this clinic with the INJURY's patient selected
        and its card in view (``?patient=`` is accepted for URL symmetry but
        never trusted). Never cached.
        """
        try:
            injury = self._check_access_to_injury(injury_id)
            clinic_event = self._require_clinic_for_fragment(kw)
        except UserError as error:
            return self._forbidden(error)
        values = self._edit_injury_form_values(injury, None, kw)
        values.update({
            'modal': True,
            'clinic_event': clinic_event,
            'return_url': self._clinic_return_url(
                clinic_event, injury.patient_id.id, anchor='clinic-injury-%s' % injury.id),
            'ctx_qs': '&clinic_id=%s' % clinic_event.id,
            'team_context_id': None,
        })
        return self._render_fragment('bemade_sports_clinic.portal_injury_form_body', values)
        
    @http.route(['/my/injury/save'], type='http', auth='user', website=True, methods=['POST'])
    def edit_injury_submit(self, **post):
        """Process the form submission to update an injury"""
        injury_id = post.get('injury_id')
        
        if not injury_id:
            return request.redirect('/my/players')
            
        injury = self._check_access_to_injury(injury_id)

        # Task 1411: PARTIAL save — the clinic dossier's per-injury note cards
        # post only the note fields (+ partial=1). Only the note fields
        # PRESENT in the payload are written; everything else on the injury
        # (diagnosis, dates, stage, TPs, visibility…) is left untouched. The
        # full edit form never sends partial=1 and keeps its behaviour below.
        if post.get('partial'):
            return self._edit_injury_partial(injury, post)

        # Get user's role
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        # Prepare values for injury update
        vals = {}
        
        # Fields everyone can update
        vals.update({
            'diagnosis': post.get('diagnosis', injury.diagnosis or ''),
            'external_notes': post.get('external_notes', injury.external_notes or ''),
        })
        
        # Handle injury date and N/A checkbox
        if post.get('injury_date_na'):
            vals['injury_date_na'] = True
            vals['injury_date'] = False  # Clear the date if N/A is checked
        else:
            vals['injury_date_na'] = False
            if post.get('injury_date'):
                vals['injury_date'] = post.get('injury_date')
        

        
        # Handle resolution dates
        if post.get('predicted_resolution_date'):
            vals['predicted_resolution_date'] = post.get('predicted_resolution_date')
        
        if post.get('resolution_date'):
            vals['resolution_date'] = post.get('resolution_date')
        
        # Handle treatment professionals (checkbox-based multi-select)
        selected_tp_ids = request.httprequest.form.getlist('treatment_professional_ids[]')
        if selected_tp_ids:
            # Convert to integers and set using Odoo's many2many syntax
            prof_ids = [int(pid) for pid in selected_tp_ids if pid]
            vals['treatment_professional_ids'] = [(6, 0, prof_ids)]
        else:
            # If no checkboxes are selected, clear the treatment professionals
            vals['treatment_professional_ids'] = [(6, 0, [])]
        
        # Fields only treatment professionals can update
        if is_treatment_prof:
            if post.get('internal_notes'):
                vals['internal_notes'] = post.get('internal_notes')

            if post.get('stage'):
                vals['stage'] = post.get('stage')

            if post.get('parental_consent'):
                vals['parental_consent'] = post.get('parental_consent')

            # Checkbox: present in form ⇒ True, absent ⇒ False
            vals['hidden_from_coaches'] = bool(post.get('hidden_from_coaches'))
                
        # Update the injury
        injury.sudo().write(vals)
        
        # Add a treatment note if provided
        if post.get('treatment_note') and is_treatment_prof:
            # Add treatment note for injury
            self._add_treatment_note(injury.patient_id, post.get('treatment_note'), injury)
        
        # Task 1412: saved FROM a clinic (the form's return_url is a clinic
        # page — the modal's form) ⇒ back to the clinic, same patient, card in
        # view. Every other caller keeps today's stay-on-the-form behaviour.
        posted_return_url = self._local_return_url(post.get('return_url'), None)
        if self._is_clinic_page_url(posted_return_url):
            return request.redirect(self._url_with_query(posted_return_url, 'success=injury_updated'))

        # Save stays on the edit form so the user can keep editing; Done (return_url) is how they leave.
        edit_url = f'/my/injury/edit?injury_id={injury_id}&success=injury_updated'
        team_id = post.get('team_id')
        if team_id:
            edit_url += f'&team_id={team_id}'   # preserve team nav context on re-render
        # …and the clinic nav context (task 1410), re-validated from the form.
        edit_url = self._with_clinic(edit_url, self._clinic_context(post))
        return request.redirect(edit_url)
        
    # Note fields a partial save may touch (task 1411). ``internal_notes`` is
    # additionally gated on the treatment-professional groups.
    _PARTIAL_INJURY_FIELDS = ('external_notes', 'internal_notes')

    def _edit_injury_partial(self, injury, post):
        """Write ONLY the note fields present in ``post`` (task 1411).

        * absent field ⇒ no-op (never clobbered with '' or the current value);
        * present field ⇒ written raw; an essentially-empty value ('' or
          whitespace) ⇒ False, a genuine clear. The injury write hook applies
          the #1404 rule: an essentially-empty or unchanged new value logs no
          note-history row;
        * ``internal_notes`` is accepted from treatment professionals only —
          a non-TP payload naming it is ignored, not refused;
        * redirects to ``return_url`` (local path only; the clinic dossier
          passes /my/clinic/<id>?patient=<pid>#clinic-injury-<iid>) with
          success=injury_updated, else to the edit form as the full save does.
        """
        is_tp = self._is_treatment_professional()
        vals = {}
        for fname in self._PARTIAL_INJURY_FIELDS:
            if fname not in post:
                continue
            if fname == 'internal_notes' and not is_tp:
                continue
            value = post.get(fname)
            vals[fname] = value if (value or '').strip() else False
        if vals:
            injury.sudo().write(vals)
        edit_url = self._with_clinic(
            f'/my/injury/edit?injury_id={injury.id}&success=injury_updated',
            self._clinic_context(post))
        return_url = self._local_return_url(post.get('return_url'), None)
        if return_url:
            return request.redirect(self._url_with_query(return_url, 'success=injury_updated'))
        return request.redirect(edit_url)

    def _add_treatment_note(self, patient, note_content, injury=None, event=None):
        """Helper method to add a treatment note to a patient, optionally linked
        to an injury and/or to the event it was captured at.

        `event` (task 1398) is what lets a note written from the clinic worklist
        be attributed to that clinic. It stays optional: every existing caller
        passes nothing and keeps creating notes with no event, unchanged.
        """
        if not note_content.strip():
            return False

        # Validate patient parameter

        # Create a new treatment note linked to patient, optionally to injury
        vals = {
            'patient_id': patient.id,
            'note': note_content,
            'date': fields.Date.today(),
            'user_id': request.env.user.id,
        }
        # Create treatment note with prepared values

        # If injury is provided, link the note to it
        if injury:
            vals['injury_id'] = injury.id

        # If the note was captured at an event (a clinic), attribute it there.
        if event:
            vals['event_id'] = event.id

        request.env['sports.treatment.note'].sudo().create(vals)

        return True
        
    @http.route(['/my/patient/notes'], type='http', auth='user', website=True)
    def view_treatment_notes(self, patient_id=None, team_id=None, **post):
        """View treatment notes for a patient (patient-centric only).

        If an optional team_id is provided, the template can render
        team-aware breadcrumbs (Teams → Team → Player → Treatment Notes).
        """
        if not patient_id:
            return request.redirect('/my/players')

        # Get user's role
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')

        # Patient context only: show all notes for this patient, with optional
        # injury links rendered in the template
        patient = self._check_access_to_patient(patient_id)

        notes = request.env['sports.treatment.note'].sudo().search(
            [('patient_id', '=', int(patient_id))],
            order='date desc, id desc',
        )

        team = None
        team_context_id = None
        if team_id:
            # Best-effort team resolution; access is still governed by
            # patient access checks above and portal record rules.
            team = request.env['sports.team'].browse(int(team_id))
            if team.exists() and team in patient.team_ids:
                team_context_id = team.id
            else:
                team = None

        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(post)
        # Where the docked « add note » form comes back to: this page, same context.
        notes_return_url = f'/my/patient/notes?patient_id={patient.id}'
        if team_context_id:
            notes_return_url += f'&team_id={team_context_id}'
        notes_return_url = self._with_clinic(notes_return_url, clinic_event)
        ctx_qs = ''
        if team_context_id:
            ctx_qs += f'&team_id={team_context_id}'
        if clinic_event:
            ctx_qs += f'&clinic_id={clinic_event.id}'

        values = {
            'injury': None,
            'notes': notes,
            'patient': patient,
            'team': team,
            'team_context_id': team_context_id,
            'clinic_event': clinic_event,
            'notes_return_url': notes_return_url,
            'ctx_qs': ctx_qs,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'patient_notes',
            'error': post.get('error'),
            'success': post.get('success'),
        }
        
        return request.render('bemade_sports_clinic.portal_treatment_notes', values)
        
    @http.route(['/my/injury/note/add'], type='http', auth='user', website=True, methods=['POST'])
    def add_treatment_note(self, **post):
        """Add a new treatment note to a patient, optionally linked to an injury.

        Honors an optional `return_url` form field so the caller (e.g.
        the new Notes tab on the player page) can redirect back to its
        origin instead of the standalone notes page.

        Task 1398 adds an optional `event_id`: the clinic worklist's docked
        capture form posts through THIS route (there is deliberately no second
        note-creation path) and the note is attributed to the clinic it was
        written at. Callers that pass no event are unaffected.
        """
        injury_id = post.get('injury_id')
        patient_id = post.get('patient_id')
        return_url = self._local_return_url(post.get('return_url'), None)
        event_id = post.get('event_id')

        if not injury_id and not patient_id:
            return request.redirect('/my/players')

        def _redirect(qs):
            target = return_url or f'/my/patient/notes?patient_id={patient_id or ""}'
            # Insert qs before any URL fragment so the #notes anchor
            # (or any other anchor) survives the redirect.
            base, frag = (target.split('#', 1) + [''])[:2]
            sep = '&' if '?' in base else '?'
            tail = f"#{frag}" if frag else ''
            return request.redirect(f"{base}{sep}{qs}{tail}")

        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return _redirect('error=permission_denied')

        note_content = post.get('note')
        if not note_content or not note_content.strip():
            return _redirect('error=empty_note')

        # Optional capture context (task 1398). A tampered/inaccessible event id
        # is REFUSED rather than silently dropped, so a note can never be
        # attributed to an event the author cannot see.
        event = None
        if event_id:
            try:
                event = self._check_access_to_event(int(event_id))
            except (TypeError, ValueError, UserError):
                return _redirect('error=permission_denied')

        if injury_id:
            injury = self._check_access_to_injury(injury_id)  # raises AccessError -> 403
            patient = injury.patient_id
            try:
                self._add_treatment_note(patient, note_content, injury, event=event)
            except UserError:
                return _redirect('error=note_failed')
            return _redirect('success=note_added')

        patient = self._check_access_to_patient(patient_id)
        self._add_treatment_note(patient, note_content, event=event)
        return _redirect('success=note_added')
        
    @http.route(['/my/injury/<int:injury_id>/notes/history'], type='http', auth='user', website=True)
    def view_injury_note_history(self, injury_id, scope=None, team_id=None, **post):
        """Read-only audit trail of injury note snapshots (task 1241).

        Access control is enforced server-side:
        - treatment professionals (portal TP group) see internal + external
          rows with an optional scope filter (?scope=internal/external/all,
          default all);
        - coaches (and any other non-TP with injury access) get EXTERNAL
          rows only, regardless of the query string;
        - users with no right to the injury get the standard 403/404 from
          _check_access_to_injury, like the neighboring injury routes.
        """
        injury = self._check_access_to_injury(injury_id)

        is_treatment_prof = request.env.user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional')

        requested_scope = scope or 'all'
        if requested_scope not in ('internal', 'external', 'all'):
            requested_scope = 'all'
        if not is_treatment_prof:
            # Coaches only ever see external notes; ignore any tampered
            # scope parameter outright.
            requested_scope = 'external'

        domain = [('injury_id', '=', injury.id)]
        if requested_scope != 'all':
            domain.append(('scope', '=', requested_scope))

        # Deliberately NOT sudo: the sports.injury.note.history portal record
        # rules re-enforce the team scoping and hide internal-scope rows from
        # coaches even if this controller filter ever regresses.
        histories = request.env['sports.injury.note.history'].search(domain)

        # Optional team navigation context for breadcrumbs (same pattern as
        # the injury-documents route; access is NOT derived from it).
        team = None
        team_context_id = None
        if team_id:
            try:
                team_rec = request.env['sports.team'].browse(int(team_id))
                if team_rec.exists():
                    team = team_rec
                    team_context_id = team_rec.id
            except Exception:
                team = None
                team_context_id = None

        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(post)
        ctx_qs = ''
        if team_context_id:
            ctx_qs += f'&team_id={team_context_id}'
        if clinic_event:
            ctx_qs += f'&clinic_id={clinic_event.id}'

        values = {
            'injury': injury,
            'patient': injury.patient_id,
            'histories': histories,
            'scope': requested_scope,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'injury_note_history',
            'team': team,
            'team_context_id': team_context_id,
            'clinic_event': clinic_event,
            'ctx_qs': ctx_qs,
        }
        return request.render('bemade_sports_clinic.portal_injury_note_history', values)

    @http.route(['/my/injury/documents'], type='http', auth='user', website=True)
    def view_injury_documents(self, injury_id=None, team_id=None, **post):
        """View documents attached to an injury.

        When an optional ``team_id`` is provided (e.g. coming from a
        team-context player page), this is used purely for navigation
        and breadcrumb context (Teams → Team → Player → Injury → Documents).
        Access is still governed entirely by injury access checks and
        record rules.
        """
        if not injury_id:
            return request.redirect('/my/players')
            
        injury = self._check_access_to_injury(injury_id)
            
        # Get documents for this injury
        documents = request.env['sports.injury.document'].sudo().search(
            [('injury_id', '=', int(injury_id))],
            order='create_date desc'
        )
        
        # Get user's role
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')

        # Optional team navigation context for breadcrumbs
        team = None
        team_context_id = None
        if team_id:
            try:
                team_rec = request.env['sports.team'].browse(int(team_id))
                if team_rec.exists():
                    team = team_rec
                    team_context_id = team_rec.id
            except Exception:
                team = None
                team_context_id = None
        
        # Document categories (aligned with model)
        categories = [
            ('medical', 'Medical'),
            ('medical_imaging', 'Medical Imaging'),
            ('prescription', 'Prescription'),
            ('other', 'Other'),
        ]
        
        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(post)
        ctx_qs = ''
        if team_context_id:
            ctx_qs += f'&team_id={team_context_id}'
        if clinic_event:
            ctx_qs += f'&clinic_id={clinic_event.id}'

        values = {
            'injury': injury,
            'documents': documents,
            'patient': injury.patient_id,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'injury_documents',
            'error': post.get('error'),
            'success': post.get('success'),
            'categories': categories,
            'team': team,
            'team_context_id': team_context_id,
            'clinic_event': clinic_event,
            'ctx_qs': ctx_qs,
        }
        
        return request.render('bemade_sports_clinic.portal_injury_documents', values)
        
    @http.route(['/my/injury/document/upload'], type='http', auth='user', website=True, methods=['POST'])
    def upload_injury_document(self, **post):
        """Upload a document for an injury"""
        injury_id = post.get('injury_id')
        
        if not injury_id:
            return request.redirect('/my/players')
            
        injury = self._check_access_to_injury(injury_id)
        # Keep the team/clinic nav context across the round-trip (task 1410).
        ctx_qs = _nav_ctx_qs(post, self._clinic_context(post))
            
        # Check if file was uploaded
        attachment = post.get('attachment')
        if not attachment:
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}{ctx_qs}&error=no_file')
            
        # Process the file
        try:
            name = attachment.filename
            safe_file_name = self._sanitize_filename(name)
            file_content = attachment.read()
            file_size = len(file_content)
            
            # Check file size (limit to 10MB)
            if file_size > 10 * 1024 * 1024:  # 10MB in bytes
                return request.redirect(f'/my/injury/documents?injury_id={injury_id}{ctx_qs}&error=file_too_large')
                
            # Create the document
            document = request.env['sports.injury.document'].sudo().create({
                'injury_id': int(injury_id),
                'patient_id': injury.patient_id.id,
                'name': post.get('document_name', name),
                'description': post.get('description', ''),
                'category': post.get('category', 'other'),
                'file_content': base64.b64encode(file_content),
                'file_name': safe_file_name,
                'created_by_id': request.env.user.id,
            })
            
            # Redirect back to documents page with success message
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}{ctx_qs}&success=document_uploaded')
            
        except Exception as e:
            _logger.error(f"Error uploading document: {e}")
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}{ctx_qs}&error=upload_failed')
            
    @http.route(['/my/injury/document/download/<int:document_id>'], type='http', auth='user')
    def download_injury_document(self, document_id, **post):
        """Download a document attached to an injury"""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        
        if not document.exists():
            raise request.not_found()
            
        try:
            # Prefer checking access via injury; if no injury, check via patient
            if document.injury_id:
                self._check_access_to_injury(document.injury_id.id)
            else:
                self._check_access_to_patient(document.patient_id.id)
        except UserError:
            raise request.not_found()
        
        # Return the file for download
        safe_name = self._sanitize_filename(document.file_name)
        return request.make_response(
            base64.b64decode(document.file_content),
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{safe_name}"'),
            ]
        )

    @http.route(['/my/patient/document/download/<int:document_id>'], type='http', auth='user')
    def download_patient_document(self, document_id, **post):
        """Download a document linked to a patient (injury optional)."""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        if not document.exists():
            raise request.not_found()
        try:
            # Access check based on patient (primary link)
            self._check_access_to_patient(document.patient_id.id)
        except UserError:
            raise request.not_found()
        safe_name = self._sanitize_filename(document.file_name)
        return request.make_response(
            base64.b64decode(document.file_content),
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{safe_name}"'),
            ]
        )

    @http.route(['/my/patient/document/upload'], type='http', auth='user', website=True, methods=['POST'])
    def upload_patient_document(self, **post):
        """Upload a document directly to a patient (injury optional)."""
        patient_id = post.get('patient_id')
        if not patient_id:
            return request.redirect('/my/players')

        patient = self._check_access_to_patient(patient_id)

        return_url = post.get('return_url') or f'/my/player?player_id={patient.id}#documents'

        def _redirect(qs):
            # Insert qs before any URL fragment so the anchor survives.
            base, frag = (return_url.split('#', 1) + [''])[:2]
            sep = '&' if '?' in base else '?'
            tail = f"#{frag}" if frag else ''
            return request.redirect(f"{base}{sep}{qs}{tail}")

        attachment = post.get('attachment')
        if not attachment:
            return _redirect('error=no_file')

        try:
            name = attachment.filename
            safe_file_name = self._sanitize_filename(name)
            file_content = attachment.read()
            file_size = len(file_content)

            # 10MB limit
            if file_size > 10 * 1024 * 1024:
                return _redirect('error=file_too_large')

            # Create patient-linked document (injury optional)
            request.env['sports.injury.document'].sudo().create({
                'patient_id': patient.id,
                'injury_id': int(post['injury_id']) if post.get('injury_id') else False,
                'name': post.get('document_name', name),
                'description': post.get('description', ''),
                'category': post.get('category', 'other'),
                'file_content': base64.b64encode(file_content),
                'file_name': safe_file_name,
                'created_by_id': request.env.user.id,
            })

            return _redirect('success=document_uploaded')

        except Exception as e:
            _logger.error(f"Error uploading patient document: {e}")
            return _redirect('error=upload_failed')
        
    @http.route(['/my/injury/document/delete/<int:document_id>'], type='http', auth='user', website=True)
    def delete_injury_document(self, document_id, **post):
        """Delete a document attached to an injury"""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        
        if not document.exists():
            raise request.not_found()
            
        try:
            # Check access to the injury this document belongs to
            injury = self._check_access_to_injury(document.injury_id.id)
        except UserError:
            raise request.not_found()
            
        # Keep the team/clinic nav context across the round-trip (task 1410).
        ctx_qs = _nav_ctx_qs(post, self._clinic_context(post))

        # Check if user is a treatment professional (only they can delete documents)
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return request.redirect(f'/my/injury/documents?injury_id={document.injury_id.id}{ctx_qs}&error=permission_denied')
            
        # Delete the document
        injury_id = document.injury_id.id
        document.sudo().unlink()
        
        # Redirect back to documents page with success message
        return request.redirect(f'/my/injury/documents?injury_id={injury_id}{ctx_qs}&success=document_deleted')
        
    @http.route(['/my/injury/verify'], type='http', auth='user', website=True, methods=['POST'])
    def verify_injury(self, injury_id, **post):
        """Verify an injury (change status from unverified to active)"""
        # Only treatment professionals / admins may verify injuries...
        if not (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                request.env.user.has_group('base.group_system')):
            return request.redirect('/my')

        # ...and only for an injury on a team they staff. Task 640 follow-up: the
        # role check alone let a TP verify ANY injury by id (per-record access was
        # never enforced). _check_access_to_injury raises UserError when the user
        # has no team overlap with the injury's patient (or it doesn't exist).
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError:
            return request.redirect('/my')

        try:
            injury.action_verify_injury()
            # Back to the player, in the same team/clinic context (task 1410).
            ctx_qs = _nav_ctx_qs(post, self._clinic_context(post))
            return request.redirect(f'/my/player?player_id={injury.patient_id.id}{ctx_qs}')
        except Exception as e:
            _logger.error(f"Error verifying injury: {e}")
            return request.redirect('/my')
            
    @http.route(['/my/injury/delete'], type='http', auth='user', website=True, methods=['POST'])
    def delete_injury(self, **post):
        """Delete an injury record (only for treatment professionals)"""
        injury_id = post.get('injury_id')
        return_url = self._local_return_url(post.get('return_url'), '/my/players')
        
        if not injury_id:
            return request.redirect(return_url)
            
        injury = self._check_access_to_injury(injury_id)
        # Keep the team/clinic nav context on the way back (task 1410).
        ctx_qs = _nav_ctx_qs(post, self._clinic_context(post))
            
        # Check if user is a treatment professional (only they can delete injuries)
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return request.redirect(f'{return_url}?error=permission_denied')
            
        # Get patient info before deletion for redirect
        patient_id = injury.patient_id.id
        
        try:
            # Delete the injury record (this will cascade delete related records)
            injury.sudo().unlink()
            _logger.info(f"Injury {injury_id} deleted by user {request.env.user.id}")
            
            # Redirect back to player page with success message
            return request.redirect(f'/my/player?player_id={patient_id}{ctx_qs}&success=injury_deleted')
            
        except Exception as e:
            _logger.error(f"Error deleting injury {injury_id}: {str(e)}")
            return request.redirect(f'{return_url}?error=delete_failed')
