from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _, fields
from odoo.exceptions import AccessError, UserError
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)


class TimesheetsPortal(CustomerPortal):
    def _parse_portal_datetime(self, val):
        """Parse a datetime-local input (YYYY-MM-DDTHH:MM[:SS]) from the portal
        as user-local time and convert to UTC string suitable for fields.Datetime.
        Returns False if empty.
        """
        if not val:
            return False
        dt = None
        try:
            if 'T' in val:
                try:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
                except ValueError:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')
            else:
                try:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M')
                except ValueError:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Fallback: let ORM try
            return val

        tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or \
                  (http.request.env.user.tz if http.request else None) or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
        except Exception:
            user_tz = pytz.UTC
        local_dt = user_tz.localize(dt)
        utc_dt = local_dt.astimezone(pytz.UTC)
        return fields.Datetime.to_string(utc_dt)

    def _prepare_home_portal_values(self, counters):
        vals = super()._prepare_home_portal_values(counters)
        if 'event_timesheets_count' in counters:
            user = http.request.env.user
            if user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or user.has_group('base.group_system'):
                # Count timesheets owned by the current user OR by an internal user sharing the same partner
                count_domain = ['|', ('user_id', '=', user.id), ('user_id.partner_id', '=', user.partner_id.id)]
                count = http.request.env['sports.event.timesheet'].search_count(count_domain)
                vals['event_timesheets_count'] = count
                _logger.debug(
                    "[TimesheetsPortal] Home counter (event_timesheets_count) user=%s(partner=%s) domain=%s -> count=%s",
                    user.id, user.partner_id.id, count_domain, count,
                )
        return vals

    def _prepare_timesheets_domain(self, user_only=True):
        user = http.request.env.user
        if not (user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or user.has_group('base.group_system')):
            # No access for non-therapists in portal
            return [('id', '=', 0)]
        domain = []
        if user_only:
            # Show records owned by the exact user or by an internal user sharing the same partner
            domain.extend(['|', ('user_id', '=', user.id), ('user_id.partner_id', '=', user.partner_id.id)])
        _logger.debug(
            "[TimesheetsPortal] _prepare_timesheets_domain user=%s(partner=%s) user_only=%s -> %s",
            user.id, user.partner_id.id, user_only, domain,
        )
        return domain

    @http.route(['/my/sc/timesheets', '/my/sc/timesheets/page/<int:page>'], type='http', auth='user', website=True)
    def view_timesheets(self, page=1, date_from=None, date_to=None, team_id=None, organization_id=None, group_by=None, sortby=None, search=None, **kw):
        _logger.warning("[TimesheetsPortal] ENTER /my/sc/timesheets page=%s", page)
        user = http.request.env.user
        if not (user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to timesheets."))

        domain = self._prepare_timesheets_domain(user_only=True)

        # Filters
        _logger.debug(
            "[TimesheetsPortal] Incoming filters user=%s(partner=%s) date_from=%s date_to=%s team_id=%s org_id=%s group_by=%s sortby=%s search=%s",
            user.id, user.partner_id.id, date_from, date_to, team_id, organization_id, group_by, sortby, search,
        )
        if date_from:
            try:
                dt = fields.Datetime.from_string(date_from)
                domain.append(('coverage_start', '>=', dt))
            except Exception:
                pass
        if date_to:
            try:
                dt = fields.Datetime.from_string(date_to)
                domain.append(('coverage_start', '<=', dt))
            except Exception:
                pass
        if team_id:
            try:
                domain.append(('event_id.team_ids', 'in', [int(team_id)]))
            except Exception:
                pass
        if organization_id:
            try:
                domain.append(('event_id.partner_id', '=', int(organization_id)))
            except Exception:
                pass
        if search:
            domain.extend(['|', '|',
                           ('event_id.name', 'ilike', search),
                           ('event_id.team_ids.name', 'ilike', search),
                           ('event_id.partner_id.name', 'ilike', search)])

        # Sorting
        sort_options = {
            'date': 'coverage_start asc',
            'date_desc': 'coverage_start desc',
            'team': 'event_id.partner_id',
            'org': 'event_id.partner_id',
            'state': 'state',
        }
        order = sort_options.get(sortby, 'coverage_start asc')

        Timesheet = http.request.env['sports.event.timesheet']
        _logger.debug("[TimesheetsPortal] Final domain=%s order=%s", domain, order)
        total = Timesheet.search_count(domain)
        _logger.debug("[TimesheetsPortal] search_count=%s", total)
        pgr = pager(url='/my/sc/timesheets', total=total, page=page, step=self._items_per_page,
                    url_args={'date_from': date_from, 'date_to': date_to, 'team_id': team_id, 'organization_id': organization_id,
                              'group_by': group_by, 'sortby': sortby, 'search': search})
        timesheets = Timesheet.search(domain, order=order, limit=self._items_per_page, offset=pgr['offset'])
        _logger.debug("[TimesheetsPortal] search result ids=%s", timesheets.ids)

        # Filters data sources
        teams = http.request.env['sports.team'].search([])
        orgs = teams.mapped('parent_id').filtered(lambda p: p).sorted('name')
        _logger.debug(
            "[TimesheetsPortal] UI sources: teams=%s orgs=%s",
            len(teams), len(orgs),
        )

        # Grouping structure
        grouped = None
        if group_by in ('date', 'organization', 'team'):
            from collections import OrderedDict
            grouped = OrderedDict()
            for ts in timesheets:
                if group_by == 'date':
                    key = (fields.Date.to_string(fields.Datetime.context_timestamp(user, ts.coverage_start).date()) if ts.coverage_start else 'No Date')
                    label = key
                elif group_by == 'organization':
                    key = ts.event_id.partner_id.id or 0
                    label = ts.event_id.partner_id.name or _('No Organization')
                else:  # team -> fallback to organization since event has multiple teams
                    key = ts.event_id.partner_id.id or 0
                    label = ts.event_id.partner_id.name or _('No Organization')
                if key not in grouped:
                    grouped[key] = {'label': label, 'items': []}
                grouped[key]['items'].append(ts)
            grouped = list(grouped.values())

        # Build user-local datetime strings for datetime-local inputs in the edit modal
        # Format: '%Y-%m-%dT%H:%M' expected by HTML input type=datetime-local
        local_dt_map = {}
        for ts in timesheets:
            def _fmt(dt):
                if not dt:
                    return ''
                try:
                    return fields.Datetime.context_timestamp(user, dt).strftime('%Y-%m-%dT%H:%M')
                except Exception:
                    # Fallback to raw string
                    return fields.Datetime.to_string(dt)[:16].replace(' ', 'T')
            local_dt_map[ts.id] = {
                'travel_start': _fmt(ts.travel_start),
                'coverage_start': _fmt(ts.coverage_start),
                'coverage_end': _fmt(ts.coverage_end),
                'travel_end': _fmt(ts.travel_end),
            }

        values = {
            'page_name': 'timesheets',
            'timesheets': timesheets,
            'pager': pgr,
            'default_url': '/my/sc/timesheets',
            'date_from': date_from,
            'date_to': date_to,
            'team_id': int(team_id) if team_id else None,
            'organization_id': int(organization_id) if organization_id else None,
            'group_by': group_by,
            'sortby': sortby,
            'search': search,
            'teams': teams,
            'organizations': orgs,
            'grouped': grouped,
            # Mapping of timesheet.id -> localized datetime strings for edit modal fields
            'timesheet_local_dt': local_dt_map,
        }
        return http.request.render('bemade_sports_clinic.portal_timesheets_list', values)

    @http.route(['/my/sc/timesheet/<int:ts_id>/edit'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def edit_timesheet(self, ts_id, **post):
        user = http.request.env.user
        if not (user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to edit timesheets."))
        ts = http.request.env['sports.event.timesheet'].browse(ts_id)
        if not ts.exists() or ts.user_id.id != user.id:
            raise AccessError(_("You can only edit your own timesheets."))
        if ts.state == 'invoiced':
            raise UserError(_('This timesheet is invoiced and cannot be edited.'))
        vals = {}
        for k in ['travel_start', 'coverage_start', 'coverage_end', 'travel_end']:
            if post.get(k):
                vals[k] = self._parse_portal_datetime(post.get(k))
        if vals:
            ts.write(vals)

        return_url = post.get('return_url')
        if return_url and isinstance(return_url, str) and '&amp;' in return_url:
            return_url = return_url.replace('&amp;', '&')
        if not return_url or return_url in ('None', 'none', 'null', 'NULL'):
            return_url = None
        if return_url and not str(return_url).startswith('/'):
            return_url = None

        target = return_url or '/my/sc/timesheets'
        separator = '&' if '?' in target else '?'
        return http.request.redirect(f'{target}{separator}updated=1')
