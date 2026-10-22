"""Task 1655 — create a player inline, from the Joueurs list and the team
page's Joueurs tab (therapists / clinic admins), like « Add Injury »:

* ``sc_player_add_panel`` (the panel values): first / last name, date of
  birth, the team(s) — the tags selector in form mode (CSV), pre-filled with
  the team page's team, or the user's only team — and an optional emergency
  contact (name + mobile together, #1645's phone rule);
* ``GET /my/app/player-check`` — the live existence check (an HTML
  fragment): matching players by name (accent-insensitive word prefixes,
  #1650's rule), refined by the date of birth; archived ones flagged; each
  row « Open », « Add to team » or « Reactivate and add » (the team page's
  guarded link route); ``data-sc-exact`` when a name + date-of-birth twin
  exists (« Create » stays disabled);
* ``POST /my/app/player/create`` — creates the player (the #1639 identity
  guard applies) and the contact, then lands on the player's Infos tab with
  ``created_player=<id>`` (the identity card opens in edit and an « Undo »
  toast is offered); a refusal comes back to the panel with the typed
  values and the message;
* ``POST /my/player/<id>/undo-create`` — the creator, within two minutes,
  while nothing else hangs on the player (injury, note, document), deletes
  it with its contacts and its To-Dos.
"""
import logging
from datetime import timedelta

from odoo import Command, _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from .access_control_mixin import parse_portal_date
from .app_search import sc_fold, sc_name_matches, sc_words
from .team_staff_portal import TeamStaffPortal

_logger = logging.getLogger(__name__)

SC_PLAYER_UNDO_MINUTES = 2
SC_PLAYER_CHECK_LIMIT = 12
FLASH_SCOPE = ('player_add',)  # also in access_control_mixin


class AppPlayerAddPortal(TeamStaffPortal):

    # ------------------------------------------------------------ check
    @http.route('/my/app/player-check', type='http', auth='user', methods=['GET'],
                multilang=False, sitemap=False)
    def sc_player_check(self, first='', last='', dob='', team_ids='', **kw):
        if not self._sc_player_add_allowed():
            raise AccessError(_("You don't have permission to create patients"))
        env = request.env
        first_words, last_words = sc_words(first), sc_words(last)
        values = {'sc_rows': [], 'sc_exact': False, 'sc_ready': bool(first_words and last_words),
                  'sc_team': False, 'sc_dob_error': False}
        try:
            day = parse_portal_date(dob) if (dob or '').strip() else False
        except ValidationError:
            day, values['sc_dob_error'] = False, True
        teams = self._sc_chosen_teams(team_ids)
        values['sc_team'] = teams[:1]
        if values['sc_ready']:
            own = set(env['sports.patient'].search(
                self._prepare_players_domain(self._prepare_teams_domain())).ids)
            admin = self._is_clinic_admin()
            Patients = env['sports.patient'].sudo().with_context(active_test=False)
            rows = []
            for row in Patients.search_read([], ['first_name', 'last_name', 'date_of_birth', 'active']):
                if not (sc_name_matches(first_words, row['first_name'])
                        and sc_name_matches(last_words, row['last_name'])):
                    continue
                if day and row['date_of_birth'] and row['date_of_birth'] != day:
                    continue
                rows.append(row)
            records = Patients.browse([row['id'] for row in rows])
            out = []
            for player in records:
                exact = bool(day and player.date_of_birth == day
                             and sc_fold(player.first_name).strip() == sc_fold(first).strip()
                             and sc_fold(player.last_name).strip() == sc_fold(last).strip())
                values['sc_exact'] = values['sc_exact'] or exact
                accessible = admin or player.id in own
                team = values['sc_team']
                out.append({
                    'id': player.id,
                    'title': player._portal_list_name(),
                    'teams': ', '.join(player.team_ids.mapped('name')),
                    'archived': not player.active,
                    'exact': exact,
                    'url': '/my/player?player_id=%s' % player.id if accessible else False,
                    'on_team': bool(team and team in player.team_ids),
                    'sort': (not exact, not player.active, sc_fold(player.last_name), sc_fold(player.first_name)),
                })
            out.sort(key=lambda r: r['sort'])
            values['sc_rows'] = out[:SC_PLAYER_CHECK_LIMIT]
        html = env['ir.ui.view']._render_template('bemade_sports_clinic.sc_player_check_results', values)
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8'),
                                                    ('Cache-Control', 'no-store')])

    # ----------------------------------------------------------- create
    def _sc_player_add_back(self, post):
        url = self._safe_return_url(post.get('return_url'), '/my/players')
        url = url.split('#')[0]
        sep = '&' if '?' in url else '?'
        if 'add=1' not in url:
            url += sep + 'add=1'
        return url

    @http.route('/my/app/player/create', type='http', auth='user', methods=['POST'], website=True)
    def sc_player_create(self, **post):
        # #1639: the identity guard for internal users too.
        request.update_context(sc_identity_guard=True)
        if not self._sc_player_add_allowed():
            return request.redirect('/my/players')
        env = request.env

        def refuse(message):
            self._portal_flash(message, post, FLASH_SCOPE)
            return request.redirect(self._sc_player_add_back(post))

        first = (post.get('first_name') or '').strip()
        last = (post.get('last_name') or '').strip()
        if not first or not last:
            return refuse(_('First name and last name are required'))
        if not (post.get('date_of_birth') or '').strip():
            return refuse(_("Date of birth is required"))
        try:
            dob = parse_portal_date(post.get('date_of_birth'))
        except ValidationError as exc:
            return refuse(exc.args[0])
        teams = self._sc_chosen_teams(post.get('team_ids'))
        if not teams and not self._is_clinic_admin():
            return refuse(_('Please select at least one team to assign to this player.'))
        ec_name = (post.get('ec_name') or '').strip()
        ec_mobile = (post.get('ec_mobile') or '').strip()
        ec_type = (post.get('ec_contact_type') or '').strip() or 'other'
        if (ec_name or ec_mobile) and not (ec_name and ec_mobile):
            return refuse(_("An emergency contact needs a name and a mobile."))
        phone_error = self._sc_phone_error(post, 'ec_mobile')
        if phone_error:
            return refuse(phone_error)
        try:
            with env.cr.savepoint():
                patient = env['sports.patient'].create_portal_patient({
                    'first_name': first, 'last_name': last, 'date_of_birth': dob,
                    'team_ids': [Command.set(teams.ids)],
                })
                if ec_name:
                    env['sports.patient.contact'].sudo().create({
                        'patient_id': patient.id, 'name': ec_name,
                        'contact_type': ec_type, 'mobile': ec_mobile,
                    })
        except (UserError, ValidationError, AccessError) as exc:
            return refuse(exc.args[0] if exc.args else _('There was an error creating the player. Please review your inputs and try again.'))
        url = '/my/player?player_id=%s' % patient.id
        team_id = post.get('context_team_id')
        if team_id and str(team_id).isdigit() and int(team_id) in teams.ids:
            url += '&team_id=%s' % int(team_id)
        url += '&tab=info&created_player=%s' % patient.id
        return request.redirect(url)

    # ------------------------------------------------------------- undo
    @http.route('/my/player/<int:player_id>/undo-create', type='http', auth='user',
                methods=['POST'], website=True)
    def sc_player_undo_create(self, player_id, **post):
        patient = request.env['sports.patient'].sudo().browse(player_id).exists()
        back = self._safe_return_url(post.get('return_url'), '/my/players')
        if not patient:
            return request.redirect(back)
        deadline = fields.Datetime.now() - timedelta(minutes=SC_PLAYER_UNDO_MINUTES)
        documents = request.env['sports.injury.document'].sudo().search_count([('patient_id', '=', patient.id)])
        notes = request.env['sports.treatment.note'].sudo().search_count([('patient_id', '=', patient.id)])
        allowed = (
            patient.create_uid == request.env.user
            and patient.create_date and patient.create_date >= deadline
            and not patient.with_context(active_test=False).injury_ids
            and not documents and not notes
        )
        if not allowed:
            _logger.info("Undo of player %s refused for user %s", patient.id, request.env.user.id)
            return request.redirect('/my/player?player_id=%s&tab=info&error=undo_expired' % patient.id)
        partner = patient.partner_id
        request.env['mail.activity'].sudo().search([
            ('res_model', '=', 'sports.patient'), ('res_id', '=', patient.id)]).unlink()
        patient.contact_ids.unlink()
        patient.unlink()
        if partner and not partner.user_ids:
            try:
                with request.env.cr.savepoint():
                    partner.unlink()
            except Exception:  # noqa: BLE001 — a partner used elsewhere stays
                _logger.info("Partner %s of an undone player kept", partner.id)
        sep = '&' if '?' in back else '?'
        return request.redirect('%s%ssuccess=player_undone' % (back, sep))
