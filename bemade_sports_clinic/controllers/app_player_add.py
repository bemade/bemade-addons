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
  exists — task 1716: a warning, « Create » waits for « Create anyway »
  (``force_create=1``); an unlikely date of birth waits for « The date is
  correct » (``dob_confirmed=1``);
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
import re
from datetime import timedelta

from odoo import Command, _, fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request
from odoo.tools import format_date

from .access_control_mixin import parse_portal_date
from ..models.sc_name_match import NEAR, NameIndex
from .app_search import sc_fold, sc_words
from .team_staff_portal import TeamStaffPortal

_logger = logging.getLogger(__name__)

SC_PLAYER_UNDO_MINUTES = 2
SC_PLAYER_CHECK_LIMIT = 12
SC_PLAYER_CHECK_MIN = 2  # letters per name part before the check searches
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
        # Adversarial review 2026-10-22: at least 2 letters per name part
        # before anything is searched.
        ready = all(len(''.join(words)) >= SC_PLAYER_CHECK_MIN for words in (first_words, last_words))
        values = {'sc_rows': [], 'sc_near_rows': [], 'sc_exact': False, 'sc_ready': ready,
                  'sc_exact_teams': '', 'sc_exact_ids': '', 'sc_team': False, 'sc_dob_error': False, 'sc_dob_warning': ''}
        try:
            day = parse_portal_date(dob) if (dob or '').strip() else False
        except ValidationError:
            day, values['sc_dob_error'] = False, True
        # Task 1716: a soft warning on an unlikely date of birth.
        values['sc_dob_warning'] = self._sc_dob_warning(day)
        teams = self._sc_chosen_teams(team_ids)
        values['sc_team'] = teams[:1]
        if values['sc_ready']:
            own_domain = self._prepare_players_domain(self._prepare_teams_domain())
            own = set(env['sports.patient'].search(own_domain).ids)
            admin = self._is_clinic_admin()
            Patients = env['sports.patient'].sudo().with_context(active_test=False)
            folded = (sc_fold(first).strip(), sc_fold(last).strip())
            # Task 1716 (owner 2026-10-26): the 2026-10-23 « date-of-birth
            # oracle » concern is waived — every suggestion, other teams'
            # included, shows its date of birth and team(s), and the typed
            # date refines / flags them all alike. A name alone never blocks.
            out = []
            exact_players = env['sports.patient'].sudo()
            # Task 1674: the shared matcher — exact / prefix (#1650's rule)
            # first, then the near matches (accents, typos, inversions,
            # swapped names, compound names) as « Similar players ». Names
            # only: the S2 rule below is unchanged for every grade.
            candidates = {row['id']: row for row in Patients.search_read(
                [], ['first_name', 'last_name', 'date_of_birth', 'active'])}
            grades = NameIndex([(rid, row['first_name'] or '', row['last_name'] or '')
                                for rid, row in candidates.items()]).match(first, last)
            for rid, grade in grades:
                row = candidates[rid]
                near = grade == NEAR
                accessible = admin or row['id'] in own
                same_name = (sc_fold(row['first_name']).strip(), sc_fold(row['last_name']).strip()) == folded
                if day and row['date_of_birth'] and row['date_of_birth'] != day:
                    continue
                exact = bool(day and row['date_of_birth'] == day and same_name)
                values['sc_exact'] = values['sc_exact'] or exact
                player = Patients.browse(row['id'])
                if exact:
                    exact_players |= player
                team = values['sc_team']
                out.append({
                    'id': player.id,
                    'title': player._portal_list_name(),
                    'teams': ', '.join(player.team_ids.mapped('name')),
                    # Task 1672 (owner): each suggestion's OWN date of birth,
                    # to tell namesakes apart — the row's data, never the
                    # typed date (S2: the answer stays the same whatever
                    # date is typed).
                    'dob': format_date(env, row['date_of_birth']) if row['date_of_birth'] else '',
                    'archived': not player.active,
                    'exact': exact,
                    'url': '/my/player?player_id=%s' % player.id if accessible else False,
                    'on_team': bool(team and team in player.team_ids),
                    'near': near,
                    'sort': (near, not exact, not player.active, sc_fold(player.last_name),
                             sc_fold(player.first_name), player.id),
                })
            if exact_players:
                values['sc_exact_teams'] = env['sports.patient']._sc_identity_twin_teams(exact_players)
                # Task 1716 (review round 2): the matched twins, so an accepted
                # « Create anyway » survives a re-check for the same identity.
                values['sc_exact_ids'] = ','.join(str(i) for i in sorted(exact_players.ids))
            out.sort(key=lambda r: r['sort'])
            out = out[:SC_PLAYER_CHECK_LIMIT]
            values['sc_rows'] = [r for r in out if not r['near']]
            values['sc_near_rows'] = [r for r in out if r['near']]
        # Task 1672 (addendum 3): in the USER's language (this JSON-ish
        # fragment route is not language-prefixed; an English user got the
        # website's French).
        html = env['ir.ui.view'].with_context(lang=env.user.lang or env.lang)._render_template(
            'bemade_sports_clinic.sc_player_check_results', values)
        return request.make_response(html, headers=[('Content-Type', 'text/html; charset=utf-8'),
                                                    ('Cache-Control', 'no-store')])

    @staticmethod
    def _sc_dob_warning(day):
        """Task 1716: a soft warning when a typed date of birth is today, in
        the future, or gives an unlikely age (under 3 or over 60); "" else.
        The user confirms it (``dob_confirmed=1``) or fixes it."""
        if not day:
            return ''
        env = request.env
        today = fields.Date.context_today(env.user)
        if day > today:
            return env._("This date of birth is in the future.")
        if day == today:
            return env._("This date of birth is today.")
        age = today.year - day.year - ((today.month, today.day) < (day.month, day.day))
        if age < 3 or age > 60:
            return env._("This date of birth gives an age of %s.", age)
        return ''

    # ----------------------------------------------------------- create
    def _sc_player_add_back(self, post):
        url = self._safe_return_url(post.get('return_url'), '/my/players')
        url = url.split('#')[0]
        if url.startswith('/my/team') and 'tab=players' not in url:
            # Owner review 2026-10-22: the panel lives on the Joueurs tab.
            url = re.sub(r'([?&])tab=[^&]*&?', r'\1', url).rstrip('&?')
            url += ('&' if '?' in url else '?') + 'tab=players'
        if 'add=1' not in url:
            url += ('&' if '?' in url else '?') + 'add=1'
        return url

    @staticmethod
    def _sc_player_add_xhr():
        """The panel's script posts with fetch: its refusals are answered as
        JSON (the panel, its values and its focus stay as they are)."""
        return request.httprequest.headers.get('X-Requested-With') == 'XMLHttpRequest'

    @http.route('/my/app/player/create', type='http', auth='user', methods=['POST'], website=True)
    def sc_player_create(self, **post):
        # #1639: the identity guard for internal users too.
        request.update_context(sc_identity_guard=True)
        if not self._sc_player_add_allowed():
            return request.redirect('/my/players')
        env = request.env

        xhr = self._sc_player_add_xhr()

        def refuse(message, field=''):
            # Owner review 2026-10-22: any refusal stays IN the panel, the
            # typed values kept, the message next to the field (or to
            # « Create »): JSON for the panel's script, else the panel
            # re-opened on its own tab with the values (flash).
            if xhr:
                return request.make_json_response(
                    {'ok': False, 'error': 'invalid', 'message': str(message), 'field': field}, status=400)
            data = {key: value for key, value in post.items() if key != 'csrf_token'}
            data['sc_error_field'] = field
            self._portal_flash(message, data, FLASH_SCOPE)
            return request.redirect(self._sc_player_add_back(post))

        first = (post.get('first_name') or '').strip()
        last = (post.get('last_name') or '').strip()
        if not first or not last:
            return refuse(_('First name and last name are required'), 'last_name' if first else 'first_name')
        if not (post.get('date_of_birth') or '').strip():
            return refuse(_("Date of birth is required"), 'date_of_birth')
        try:
            dob = parse_portal_date(post.get('date_of_birth'))
        except ValidationError as exc:
            return refuse(exc.args[0], 'date_of_birth')
        # Task 1716: an unlikely date of birth needs the user's confirmation.
        dob_warning = self._sc_dob_warning(dob)
        if dob_warning and post.get('dob_confirmed') != '1':
            return refuse(_("%s Confirm it or fix it.", dob_warning), 'date_of_birth')
        teams = self._sc_chosen_teams(post.get('team_ids'))
        if not teams and not self._is_clinic_admin():
            return refuse(_('Please select at least one team to assign to this player.'))
        ec_name = (post.get('ec_name') or '').strip()
        ec_mobile = (post.get('ec_mobile') or '').strip()
        ec_type = (post.get('ec_contact_type') or '').strip() or 'other'
        if (ec_name or ec_mobile) and not (ec_name and ec_mobile):
            return refuse(_("An emergency contact needs a name and a mobile."), 'ec_mobile' if ec_name else 'ec_name')
        # Security review 2026-10-23: a value outside the selection is a field
        # error in the panel (it used to fail later, as a 500).
        if ec_name and ec_type not in env['sports.patient.contact']._fields['contact_type'].get_values(env):
            return refuse(_("Please choose a relationship from the list."), 'ec_contact_type')
        phone_error = self._sc_phone_error(post, 'ec_mobile')
        if phone_error:
            return refuse(phone_error, 'ec_mobile')
        if post.get('force_create') == '1':
            # Task 1716: « Créer quand même » over a name + date-of-birth twin.
            env = env(context=dict(env.context, sc_identity_force_create=True))
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
        if xhr:
            return request.make_json_response({'ok': True, 'redirect': url})
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
        # Task 1432: archived documents count too (the unlink would cascade).
        documents = request.env['sports.injury.document'].sudo().with_context(
            active_test=False).search_count([('patient_id', '=', patient.id)])
        notes = request.env['sports.treatment.note'].sudo().search_count([('patient_id', '=', patient.id)])
        allowed = (
            patient.create_uid == request.env.user
            and patient.create_date and patient.create_date >= deadline
            and not patient.with_context(active_test=False).injury_ids
            and not documents and not notes
        )
        if not allowed:
            _logger.info("Undo of player %s refused for user %s", patient.id, request.env.user.id)
            # Task 1663: the player's own message (not the injury one).
            return request.redirect(
                '/my/player?player_id=%s&tab=info&error=player_undo_expired' % patient.id)
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
        # Task 1663: a toast on whichever app page the user goes back to
        # (the team page, the players list…), « Création du joueur annulée. »
        request.session['notification'] = {
            'type': 'success',
            'title': '',
            'message': request.env._("Player creation undone."),
            'sticky': False,
        }
        return request.redirect(back)
