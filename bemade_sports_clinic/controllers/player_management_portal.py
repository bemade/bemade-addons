import logging
from odoo import http, fields, _, Command
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from .access_control_mixin import AccessControlMixin
from .app_shell import AppShellMixin, sc_app_page
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class PlayerManagementPortal(CustomerPortal, AccessControlMixin, AppShellMixin):
    """Controller for player management functionality in the portal"""
    
    # Access control methods now inherited from AccessControlMixin
    
    @http.route(['/my/player/create'], type='http', auth='user', website=True)
    @sc_app_page
    def create_player_form(self, **get):
        """Task 1541: an old link / bookmark of the retired create page —
        the Players list's inline « create a player » panel (task 1655)."""
        return request.redirect('/my/players?add=1', code=301)

    @http.route(['/my/player/create/save'], type='http', auth='user', website=True, methods=['POST'])
    def create_player_submit(self, **post):
        """Handle standalone player creation submit."""
        # Task 1639: the identity guard (duplicates) for internal users too.
        request.update_context(sc_identity_guard=True)
        user = request.env.user
        is_treatment_prof = self._is_treatment_professional()
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        first_name = (post.get('first_name') or '').strip()
        last_name = (post.get('last_name') or '').strip()
        dob = (post.get('date_of_birth') or '').strip()

        if not first_name or not last_name:
            self._portal_flash(_('First name and last name are required'), None, ('player_create',))
            return request.redirect('/my/player/create')

        # Team selection (optional). Restrict to staff teams to avoid tampering
        try:
            # One value per checkbox (portal form) or one comma-separated
            # value (the app's tag picker, task 1726).
            selected_team_ids = [int(tid) for raw in request.httprequest.form.getlist('team_ids')
                                 for tid in str(raw).split(',') if tid.strip()]
        except Exception:
            selected_team_ids = []
        allowed_team_ids = self._team_targets().ids
        selected_team_ids = [tid for tid in selected_team_ids if tid in allowed_team_ids]

        # Require at least one team for treatment professionals to ensure access control
        if is_treatment_prof and not selected_team_ids:
            self._portal_flash(_('Please select at least one team to assign to this player.'), None, ('player_create',))
            return request.redirect('/my/player/create')

        # Task 1645: the player's phone and the emergency contact's mobile.
        phone_error = self._sc_phone_error(post, 'phone', 'ec_mobile')
        if phone_error:
            self._portal_flash(phone_error, None, ('player_create',))
            return request.redirect('/my/player/create')

        # Validate DOB format and range if provided
        if dob:
            try:
                # Will raise if the date is not a valid string for a Date field
                dob_date = fields.Date.to_date(dob)
            except Exception:
                _logger.info('Invalid date_of_birth provided on create: %s', dob)
                self._portal_flash(_('Please enter a valid Date of Birth (YYYY-MM-DD).'), None, ('player_create',))
                return request.redirect('/my/player/create')

            # Range checks: not in the future, not older than 120 years
            today = fields.Date.context_today(request.env.user) or fields.Date.today()
            min_dob = today - relativedelta(years=120)
            if dob_date > today or dob_date < min_dob:
                self._portal_flash(
                    _('Date of Birth must not be in the future and not be more than 120 years ago.'), None, ('player_create',))
                return request.redirect('/my/player/create')

        vals = {
            'first_name': first_name,
            'last_name': last_name,
        }
        if dob:
            vals['date_of_birth'] = dob
        # Optional contact and address fields
        for key in ['email', 'phone', 'street', 'street2', 'city', 'zip']:
            if key in post:
                vals[key] = post.get(key) or False
        if post.get('state_id'):
            try:
                vals['state_id'] = int(post.get('state_id'))
            except Exception:
                pass
        if post.get('country_id'):
            try:
                vals['country_id'] = int(post.get('country_id'))
            except Exception:
                pass
        # Player position - any portal user with access (incl. coaches) can set
        if 'position' in post:
            _pos = (post.get('position') or '').strip()
            vals['position'] = _pos if _pos else False
        # Jersey number (task 1421) - same audience as position; the model
        # normalises it (« #12 » → « 12 », blank → False).
        if 'jersey_number' in post:
            _num = (post.get('jersey_number') or '').strip()
            vals['jersey_number'] = _num if _num else False

        # Additional fields for treatment professionals
        if is_treatment_prof:
            if selected_team_ids:
                vals['team_ids'] = [(6, 0, list(set(selected_team_ids)))]
            # Task 1630: the allergy / medical-alert block.
            vals.update(request.env['sports.patient']._sc_medical_vals_from_post(post))
            if 'team_info_notes' in post:
                _notes = (post.get('team_info_notes') or '').strip()
                vals['team_info_notes'] = _notes if _notes else False
            if post.get('match_status'):
                vals['match_status'] = post.get('match_status')
            if post.get('practice_status'):
                vals['practice_status'] = post.get('practice_status')
            # Training recommendation is TP-authored (coach-read only). Accept
            # it only inside this is_treatment_prof gate so a coach POST cannot
            # set it.
            if 'training_recommendation' in post:
                _tr = (post.get('training_recommendation') or '').strip()
                vals['training_recommendation'] = _tr if _tr else False

        # Use public create method with permission checks
        try:
            # Task 1600: a refused create leaves nothing behind (the partner
            # is created before the patient).
            with request.env.cr.savepoint():
                patient = request.env['sports.patient'].create_portal_patient(vals)
        except ValidationError as ve:
            _logger.info('ValidationError during player create: %s', ve)
            self._portal_flash(str(ve) or _('Invalid combination of match and practice status.'), None, ('player_create',))
            return request.redirect('/my/player/create')
        except Exception as e:
            _logger.exception('Error creating patient from portal create')
            self._portal_flash(
                self._user_error_text(e, 'patient')
                or _('There was an error creating the player. Please review your inputs and try again.'), None, ('player_create',))
            return request.redirect('/my/player/create')

        # Optionally create a primary emergency contact if provided (TPs and coaches)
        if is_treatment_prof or is_coach:
            ec_name = (post.get('ec_name') or '').strip()
            ec_type = (post.get('ec_contact_type') or '').strip()
            if ec_name and ec_type:
                contact_vals = {
                    'patient_id': patient.id,
                    'name': ec_name,
                    'contact_type': ec_type,
                }
                if post.get('ec_mobile'):
                    contact_vals['mobile'] = post.get('ec_mobile')
                if post.get('ec_email'):
                    contact_vals['email'] = post.get('ec_email')
                try:
                    request.env['sports.patient.contact'].sudo().create(contact_vals)
                except Exception:
                    _logger.exception('Failed to create primary emergency contact during player create')

        return request.redirect(
            self._with_jersey_warning(f"/my/player?player_id={patient.id}", patient))

    @staticmethod
    def _with_jersey_warning(url, patient):
        """Task 1421: append ``warning=duplicate_number`` to a post-save
        redirect when the player now shares a jersey number with an active
        teammate. Soft: the save already happened; the player page renders the
        banner (naming the other player) from live data, any other landing
        page ignores the parameter."""
        if patient.exists() and patient.sudo()._jersey_duplicates():
            return url + ('&' if '?' in url else '?') + 'warning=duplicate_number'
        return url

    @http.route(['/my/player/edit'], type='http', auth='user', website=True)
    @sc_app_page
    def edit_player_form(self, patient_id=None, **post):
        """Task 1541: an old link / bookmark of the retired edit page — the
        player's Info tab, where every field is edited inline (owner review
        2026-10-10), in the validated team / clinic context.

        Review 2026-11-26: no id → the players list; a malformed or unknown
        id → not found (``player_id`` is accepted too)."""
        patient_id = patient_id or post.get('player_id')
        if not patient_id:
            return request.redirect('/my/players')
        patient = self._check_access_to_patient(patient_id)
        teams = patient.team_ids
        # A team context only if the user is staff on that team and the
        # player is a member.
        raw_team_ctx = request.httprequest.args.get('team_id') or post.get('team_id')
        team_context_id = None
        if raw_team_ctx:
            try:
                cand_id = int(raw_team_ctx)
                # Validate access via shared mixin helper
                team_obj = self._check_team_access(cand_id, check_staff=True)
                if team_obj and team_obj in teams:
                    team_context_id = cand_id
            except Exception:
                # Ignore invalid team context silently
                team_context_id = None

        # Clinic navigation context (task 1410): validated, dropped if invalid.
        clinic_event = self._clinic_context(post)

        return request.redirect(self._sc_player_tab_url(
            patient.id, 'info', team_context_id, clinic_event), code=301)

    @http.route(['/my/player/save'], type='http', auth='user', website=True, methods=['POST'])
    def edit_player_submit(self, **post):
        """Process the form submission to update player information.

        Task 1600:
        * a validation error flashes the posted form for THIS player only
          (scope ``('player_edit', id)``, expiring);
        * the patient write and the team removals run in one savepoint — a
          refused save changes nothing;
        * first / last name and date of birth are written only when they
          changed; changing an existing value needs ``identity_confirmed=1``
          (the form's confirm step), which the model records on the file;
        * an unticked team (one the user may assign) goes through the
          official removal path (``remove_from_team(clear_pending=True)``);
          the player's other teams are never touched;
        * a save that leaves the user without access to the player lands on
          the players list with a toast, never on a 403.
        """
        # Task 1639: the identity guard for internal users too.
        request.update_context(sc_identity_guard=True)
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        patient = self._check_access_to_patient(patient_id)
        flash_scope = ('player_edit', patient.id)

        def flash(message):
            self._portal_flash(message, None, flash_scope)

        # Validation round-trips go back to the edit form in the same team /
        # clinic nav context (task 1410); both are re-validated by the form.
        edit_url = '/my/player/edit?patient_id=%s' % patient.id
        if post.get('team_id'):
            try:
                edit_url += '&team_id=%s' % int(post.get('team_id'))
            except (TypeError, ValueError):
                pass
        edit_url = self._with_clinic(edit_url, self._clinic_context(post))
            
        # Check if user is a treatment professional or coach
        is_treatment_prof = self._is_treatment_professional()
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Task 1645: the phone and the emergency contact's mobile.
        phone_error = self._sc_phone_error(post, 'phone', 'ec_mobile')
        if phone_error:
            flash(phone_error)
            return request.redirect(edit_url)

        # If DOB is being changed/provided, validate format upfront to avoid unhelpful errors
        dob_str = (post.get('date_of_birth') or '').strip()
        dob_date = None
        if dob_str:
            try:
                dob_date = fields.Date.to_date(dob_str)
            except Exception:
                flash(_('Please enter a valid Date of Birth (YYYY-MM-DD).'))
                return request.redirect(edit_url)

            # Range checks: not in the future, not older than 120 years
            today = fields.Date.context_today(request.env.user) or fields.Date.today()
            min_dob = today - relativedelta(years=120)
            if dob_date > today or dob_date < min_dob:
                flash(_('Date of Birth must not be in the future and not be more than 120 years ago.'))
                return request.redirect(edit_url)

        # Prepare values for patient update
        vals = {}
        current = patient.sudo()
        
        # Basic information - any portal user with access can update these.
        # Task 1600: only what changed (an unchanged name is not re-written).
        first_name = (post.get('first_name') or '').strip()
        last_name = (post.get('last_name') or '').strip()
        if first_name and last_name:
            if first_name != (current.first_name or '').strip():
                vals['first_name'] = first_name
            if last_name != (current.last_name or '').strip():
                vals['last_name'] = last_name
            
        # Contact information
        if post.get('email'):
            vals.update({
                'email': post.get('email'),
            })
            
        if post.get('phone'):
            vals.update({
                'phone': post.get('phone'),
            })
            
        # Address information - any portal user with access can update these
        address_fields = ['street', 'street2', 'city', 'zip']
        for field in address_fields:
            if field in post:
                vals[field] = post.get(field) or False
                
        # Handle state and country selections
        if post.get('state_id'):
            try:
                state_id = int(post.get('state_id'))
                vals['state_id'] = state_id
            except (ValueError, TypeError):
                pass  # Invalid state_id, skip
                
        if post.get('country_id'):
            try:
                country_id = int(post.get('country_id'))
                vals['country_id'] = country_id
            except (ValueError, TypeError):
                pass  # Invalid country_id, skip

        # Player position - any portal user with access (incl. coaches) can update
        if 'position' in post:
            _pos = (post.get('position') or '').strip()
            vals['position'] = _pos if _pos else False
        # Jersey number (task 1421) - same audience as position.
        if 'jersey_number' in post:
            _num = (post.get('jersey_number') or '').strip()
            vals['jersey_number'] = _num if _num else False

        removed_teams = request.env['sports.team']
        # Additional fields that only treatment professionals can update
        if is_treatment_prof:
            # Team assignments via the checklist. Task 1600: a diff against the
            # player's teams that the user may assign — added teams are linked,
            # unticked ones go through the official removal path below, and the
            # player's other teams (not the user's to touch) are kept.
            try:
                team_id_list = {int(tid) for tid in request.httprequest.form.getlist('team_ids')}
            except Exception:
                team_id_list = set()
            allowed = self._team_targets()
            posted = allowed.filtered(lambda t: t.id in team_id_list)
            current_teams = current.team_ids
            added = posted - current_teams
            removed_teams = (current_teams & allowed) - posted
            if added:
                vals['team_ids'] = [Command.link(team.id) for team in added]
            if dob_date and dob_date != current.date_of_birth:
                vals['date_of_birth'] = dob_date
                
            # Medical information (task 1630: the allergy / medical-alert block)
            vals.update(request.env['sports.patient']._sc_medical_vals_from_post(post))
                
            if 'team_info_notes' in post:
                _notes = (post.get('team_info_notes') or '').strip()
                vals.update({
                    'team_info_notes': _notes if _notes else False,
                })
                
            # Status fields
            if post.get('match_status'):
                vals.update({
                    'match_status': post.get('match_status'),
                })
                
            if post.get('practice_status'):
                vals.update({
                    'practice_status': post.get('practice_status'),
                })

            if 'last_consultation_date' in post:
                _lcd = (post.get('last_consultation_date') or '').strip()
                vals['last_consultation_date'] = _lcd if _lcd else False

            # Training recommendation is TP-authored (coach-read only). Accept
            # it only inside this is_treatment_prof gate so a coach POST cannot
            # set it.
            if 'training_recommendation' in post:
                _tr = (post.get('training_recommendation') or '').strip()
                vals['training_recommendation'] = _tr if _tr else False

        # Update the patient - no sudo needed as field-level security is in
        # place. Task 1600: the identity confirmation is passed on only when
        # the form's confirm step posted it.
        writer = patient
        if post.get('identity_confirmed') == '1':
            writer = writer.with_context(sc_identity_confirmed=True)
        if vals or removed_teams:
            try:
                with request.env.cr.savepoint():
                    if vals:
                        writer.write(vals)
                    for team in removed_teams:
                        patient.remove_from_team(team.id, clear_pending=True)
                    patient.flush_recordset()
            except ValidationError as ve:
                flash(str(ve) or _('Invalid combination of match and practice status.'))
                return request.redirect(edit_url)
            except Exception as e:
                flash(self._user_error_text(e, 'patient') or _('An unexpected error occurred.'))
                return request.redirect(edit_url)

        # Task 1600: unticking the user's last team on this player ends their
        # access — land on the players list with a toast, never on a 403.
        try:
            self._check_access_to_patient(patient.id)
        except (AccessError, MissingError):
            request.session['notification'] = {
                'type': 'success',
                'title': _('Player updated'),
                'message': _("The player is no longer on any of your teams."),
                'sticky': False,
            }
            return request.redirect('/my/players')

        # Update or create primary emergency contact (TPs and coaches), regardless of patient field changes
        if is_treatment_prof or is_coach:
            ec_name = (post.get('ec_name') or '').strip()
            ec_type = (post.get('ec_contact_type') or '').strip()
            ec_mobile = (post.get('ec_mobile') or '').strip()
            ec_email = (post.get('ec_email') or '').strip()

            # If any EC field provided, attempt update/create
            if any([ec_name, ec_type, ec_mobile, ec_email]):
                primary_contact = request.env['sports.patient.contact'].search([
                    ('patient_id', '=', patient.id)
                ], order='sequence,id', limit=1)

                if primary_contact:
                    update_vals = {}
                    # Only update name/type if provided (avoid clearing required selection)
                    if ec_name:
                        update_vals['name'] = ec_name
                    if ec_type:
                        update_vals['contact_type'] = ec_type
                    # For mobile/email, explicitly set to value or False to clear
                    if 'ec_mobile' in post:
                        update_vals['mobile'] = ec_mobile or False
                    if 'ec_email' in post:
                        update_vals['email'] = ec_email or False
                    if update_vals:
                        try:
                            primary_contact.sudo().write(update_vals)
                        except Exception:
                            _logger.exception('Failed to update primary emergency contact for patient %s', patient.id)
                else:
                    # Create only if we have minimally required fields
                    if ec_name and ec_type:
                        create_vals = {
                            'patient_id': patient.id,
                            'name': ec_name,
                            'contact_type': ec_type,
                            'sequence': 0,
                        }
                        if 'ec_mobile' in post:
                            create_vals['mobile'] = ec_mobile or False
                        if 'ec_email' in post:
                            create_vals['email'] = ec_email or False
                        try:
                            request.env['sports.patient.contact'].sudo().create(create_vals)
                        except Exception:
                            _logger.exception('Failed to create primary emergency contact for patient %s', patient.id)

        return_url = self._local_return_url(
            post.get('return_url'), f'/my/player?player_id={patient_id}')
        if 'jersey_number' in vals or 'team_ids' in vals:
            return_url = self._with_jersey_warning(return_url, patient)
        return request.redirect(return_url)
    
    # ------------------------------------------------------------------
    # Task 1411: quick edit from the clinic dossier
    # ------------------------------------------------------------------
    # The only fields the quick route may touch. Anything else in the payload
    # is ignored — the full edit form (/my/player/save) is the place for it.
    _QUICK_FIELDS = ('training_recommendation', 'match_status', 'practice_status')
    # Mirror of sports.patient.constrain_match_and_practice_status: checked
    # BEFORE the write so an invalid pair writes nothing (the constraint is
    # still the gate of last resort — a ValidationError is caught too).
    _VALID_STATUS_COMBOS = {('yes', 'yes'), ('no', 'yes'), ('no', 'no_contact'), ('no', 'no')}

    @http.route(['/my/player/<int:patient_id>/quick'], type='http', auth='user',
                website=True, methods=['POST'])
    def quick_edit_player(self, patient_id, **post):
        """Inline save of the training recommendation and/or the match /
        practice statuses (task 1411, clinic dossier). Treatment
        professionals only; team-gated like every patient route.

        * only the whitelisted fields PRESENT in the payload are written;
        * an unknown selection value or an invalid match/practice combination
          writes nothing and redirects back with error=invalid_status_combo
          (+ the refused pair, so the form can re-show it);
        * redirects to ``return_url`` (local path only) with success=player_updated,
          else to the player page. Tracking on sports.patient logs the change
          in chatter exactly as the full edit form does.
        """
        patient = self._check_access_to_patient(patient_id)
        if not self._is_treatment_professional():
            raise AccessError(_("Only treatment professionals can edit these fields."))

        return_url = self._local_return_url(
            post.get('return_url'), f'/my/player?player_id={patient.id}')

        vals = {}
        if 'training_recommendation' in post:
            _tr = (post.get('training_recommendation') or '').strip()
            vals['training_recommendation'] = _tr if _tr else False

        Patient = request.env['sports.patient']
        match_keys = {k for k, _l in Patient._fields['match_status'].selection}
        practice_keys = {k for k, _l in Patient._fields['practice_status'].selection}
        match = patient.match_status
        practice = patient.practice_status
        statuses_posted = False
        if 'match_status' in post:
            match = post.get('match_status')
            statuses_posted = True
        if 'practice_status' in post:
            practice = post.get('practice_status')
            statuses_posted = True
        if statuses_posted:
            if (match not in match_keys or practice not in practice_keys
                    or (match, practice) not in self._VALID_STATUS_COMBOS):
                return request.redirect(self._url_with_query(
                    return_url,
                    'error=invalid_status_combo&match_status=%s&practice_status=%s' % (
                        match if match in match_keys else '',
                        practice if practice in practice_keys else '')))
            vals['match_status'] = match
            vals['practice_status'] = practice

        if vals:
            try:
                patient.write(vals)
            except ValidationError:
                return request.redirect(self._url_with_query(
                    return_url, 'error=invalid_status_combo'))
        return request.redirect(self._url_with_query(return_url, 'success=player_updated'))

    @http.route(['/my/player/contact/add'], type='http', auth='user', website=True)
    @sc_app_page
    def add_contact_form(self, patient_id=None, **post):
        """Task 1541: an old link / bookmark of the retired add-contact page —
        the contacts are added inline on the player's Info tab (owner review
        2026-10-10). No id → the players list; a malformed one → not found."""
        if not patient_id:
            return request.redirect('/my/players')
        patient = self._check_access_to_patient(patient_id)
        return request.redirect(self._sc_player_tab_url(patient.id, 'info'), code=301)

    @http.route(['/my/player/contact/save'], type='http', auth='user', website=True, methods=['POST'])
    def add_contact_submit(self, **post):
        """Process the form submission to add a new emergency contact"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        patient = self._check_access_to_patient(patient_id)
            
        # Check if user is a treatment professional or coach
        is_treatment_prof = self._is_treatment_professional()
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Only TPs and coaches can add emergency contacts
        if not (is_treatment_prof or is_coach):
            return request.redirect(f'/my/player?player_id={patient_id}')
        
        # Required fields
        if not post.get('name') or not post.get('contact_type'):
            self._portal_flash(_("Name and contact type are required fields"), post, ('contact_add', patient.id))
            return request.redirect('/my/player/contact/add?patient_id=%s' % patient_id)
        # Task 1645: a mobile the clinic's phone rule refuses.
        phone_error = self._sc_phone_error(post, 'mobile')
        if phone_error:
            self._portal_flash(phone_error, post, ('contact_add', patient.id))
            return request.redirect('/my/player/contact/add?patient_id=%s' % patient_id)
        
        # Prepare values for contact creation
        vals = {
            'patient_id': int(patient_id),
            'name': post.get('name'),
            'contact_type': post.get('contact_type'),
        }
        
        # Optional fields
        if post.get('mobile'):
            vals['mobile'] = post.get('mobile')
        if post.get('email'):
            vals['email'] = post.get('email')
        
        # Create the contact
        request.env['sports.patient.contact'].sudo().create(vals)

        # Respect a return_url field so the form lands the user back
        # on the originating tab (e.g. ".../my/player?...#contacts").
        return_url = self._safe_return_url(
            post.get('return_url'), f'/my/player?player_id={patient_id}#contacts')
        return request.redirect(return_url)
    
    @http.route(['/my/player/contact/edit'], type='http', auth='user', website=True)
    @sc_app_page
    def edit_contact_form(self, contact_id=None, **post):
        """Task 1541: an old link / bookmark of the retired edit-contact page
        — the contacts are edited inline on the player's Info tab. No id →
        the players list; a malformed or unknown id → not found."""
        if not contact_id:
            return request.redirect('/my/players')
        contact = request.env['sports.patient.contact'].browse(self._sc_record_id(contact_id))
        if not contact.exists():
            raise request.not_found()
        patient = self._check_access_to_patient(contact.patient_id.id)
        return request.redirect(self._sc_player_tab_url(patient.id, 'info'), code=301)

    @http.route(['/my/player/contact/update'], type='http', auth='user', website=True, methods=['POST'])
    def edit_contact_submit(self, **post):
        """Process the form submission to update an emergency contact"""
        contact_id = post.get('contact_id')
        
        if not contact_id:
            return request.redirect('/my/players')
            
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        patient = self._check_access_to_patient(contact.patient_id.id)
            
        # Check if user is a treatment professional
        is_treatment_prof = self._is_treatment_professional()
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Only TPs and coaches can edit emergency contacts
        if not (is_treatment_prof or is_coach):
            return request.redirect(f'/my/player?player_id={patient.id}')
        
        # Required fields
        if not post.get('name') or not post.get('contact_type'):
            self._portal_flash(_("Name and contact type are required fields"), post, ('contact_edit', contact.id))
            return request.redirect('/my/player/contact/edit?contact_id=%s' % contact.id)
        # Task 1645: a mobile the clinic's phone rule refuses.
        phone_error = self._sc_phone_error(post, 'mobile')
        if phone_error:
            self._portal_flash(phone_error, post, ('contact_edit', contact.id))
            return request.redirect('/my/player/contact/edit?contact_id=%s' % contact.id)
        
        # Prepare values for contact update
        vals = {
            'name': post.get('name'),
            'contact_type': post.get('contact_type'),
        }
        
        # Optional fields
        if post.get('mobile'):
            vals['mobile'] = post.get('mobile')
        else:
            vals['mobile'] = False
        
        if post.get('email'):
            vals['email'] = post.get('email')
        else:
            vals['email'] = False
        
        # Update the contact
        contact.sudo().write(vals)

        return_url = self._safe_return_url(
            post.get('return_url'), f'/my/player?player_id={patient.id}#contacts')
        return request.redirect(return_url)
    
    @http.route(['/my/player/contact/delete'], type='http', auth='user', website=True, methods=['POST'])
    def delete_contact(self, contact_id, **post):
        """Delete an emergency contact"""
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        patient = self._check_access_to_patient(contact.patient_id.id)
            
        # Check if user is a treatment professional
        is_treatment_prof = self._is_treatment_professional()
        
        return_url = self._safe_return_url(
            post.get('return_url'), f'/my/player?player_id={patient.id}#contacts')

        # Regular coaches shouldn't be able to delete emergency contacts
        if not is_treatment_prof:
            return request.redirect(return_url)

        # Delete the contact
        contact.sudo().unlink()

        return request.redirect(return_url)
