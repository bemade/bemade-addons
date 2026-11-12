# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""``portal.kit`` — the per-database registries of the portal app shell.

Read this before adding a role, a menu entry, a visibility key or a page.

Hooks (extend them with ``super()`` in an ``_inherit = 'portal.kit'``)
-----------------------------------------------------------------------
* ``_pk_roles()``       ``{role: {'groups': (xmlid, ...), 'app': bool, ...}}``
* ``_pk_nav()``         ``[pk_nav(...), ...]``
* ``_pk_visibility()``  ``{key: {'include', 'exclude', 'system', 'model', 'field'}}``
* ``_pk_pages()``       ``[Page(...), ...]``
* ``_pk_save_specs()``  ``{model: spec}`` (task 5199: the save engine, see
  ``tools/save.py``; the kit declares ``mail.activity``)
* ``_pk_fragment_fillers()`` ``[callable(found, keys), ...]`` (task 5199:
  fill the fragments a render missed; never cached)
* ``_pk_activity_can_act(activity)`` / ``_pk_activity_assignable_users(activity)``
  (task 5199: the ``mail.activity`` spec's rules; per user, never cached)

Each hook is built ONCE per registry (``tools.ormcache``) and frozen: the
result is shared by every user and request of the database, so a hook holds
code only — never anything that depends on the user, a record or the
request. Per-user roles go in ``res.users._pk_extra_roles()`` (never
cached). An addon's entries live in its own class of this model, so they
exist only in the databases where it is installed (no module-level state).

An entry re-declared under an existing key replaces it in place.
"""
from urllib.parse import parse_qs, urlsplit

from odoo import api, models, tools

from ..tools import (
    pk_activity_save_spec, pk_freeze, pk_id_key, pk_is_visible, pk_refresh_patterns,
    pk_safe_return_url,
)


def _by_key(items, key_of):
    """``{key: item}`` in first-declaration order, later items replacing."""
    result = {}
    for item in items:
        result[key_of(item)] = item
    return result


class PortalKit(models.AbstractModel):
    _name = 'portal.kit'
    _description = 'Portal Kit Registries'

    # ------------------------------------------------------------------
    # Hooks (consumers extend these with super())
    # ------------------------------------------------------------------
    @api.model
    def _pk_roles(self):
        return {}

    @api.model
    def _pk_nav(self):
        return []

    @api.model
    def _pk_visibility(self):
        return {}

    @api.model
    def _pk_pages(self):
        return []

    @api.model
    def _pk_save_specs(self):
        """Task 5199 (P4a): ``{model: spec}``, what the save route may write
        (``tools/save.py``). The kit declares ``mail.activity``."""
        return {'mail.activity': pk_activity_save_spec()}

    @api.model
    def _pk_fragment_fillers(self):
        """Task 5199 (P4a): ``[callable(found, keys)]``, run on a fragment
        answer: each may add to ``found`` (``{key: outer html}``) keys of
        ``keys`` the render did not carry. Not cached (cheap)."""
        return []

    @api.model
    def _pk_activity_can_act(self, activity):
        """Task 5199 (P4a): may the current user edit ``activity`` through
        the save route? Default: their own write right (ACL + rules)."""
        activity = activity.exists()
        return bool(activity) and activity.has_access('write')

    @api.model
    def _pk_activity_assignable_users(self, activity):
        """Task 5199 (P4a): the users ``activity`` may be assigned to by the
        current user. Default: the internal users and the user themself."""
        return self.env['res.users'].sudo().search([('share', '=', False)]) | self.env.user

    # ------------------------------------------------------------------
    # Cached, frozen registries (one per database registry)
    # ------------------------------------------------------------------
    @api.model
    @tools.ormcache()
    def _pk_get_roles(self):
        roles = {}
        for role, spec in self._pk_roles().items():
            spec = dict(spec)
            spec['groups'] = tuple(spec.get('groups') or ())
            spec['app'] = bool(spec.get('app', True))
            roles[role] = pk_freeze(spec)
        return pk_freeze(roles)

    @api.model
    @tools.ormcache()
    def _pk_get_nav(self):
        entries = _by_key(self._pk_nav(), lambda entry: entry['key'])
        return tuple(pk_freeze(entry) for entry in entries.values())

    @api.model
    @tools.ormcache()
    def _pk_get_visibility(self):
        return pk_freeze({key: pk_freeze(spec) for key, spec in self._pk_visibility().items()})

    @api.model
    @tools.ormcache()
    def _pk_get_pages(self):
        return pk_freeze(_by_key(self._pk_pages(), lambda page: page.key))

    @api.model
    @tools.ormcache()
    def _pk_get_save_specs(self):
        return pk_freeze({model: pk_freeze(spec) for model, spec in self._pk_save_specs().items()})

    # ------------------------------------------------------------------
    # Save engine (task 5199)
    # ------------------------------------------------------------------
    @api.model
    def pk_save_specs(self):
        """``{model: spec}`` (read-only)."""
        return self._pk_get_save_specs()

    @api.model
    def pk_save_spec(self, model):
        """The save spec of ``model`` (read-only), or None."""
        return self._pk_get_save_specs().get(model)

    @api.model
    def pk_refresh_patterns(self, record, field):
        """The fragment key patterns a save of ``record.field`` makes stale."""
        return pk_refresh_patterns(self.pk_save_spec(record._name), record, field)

    # ------------------------------------------------------------------
    # Roles
    # ------------------------------------------------------------------
    @api.model
    def pk_roles(self):
        """The declared roles (read-only)."""
        return self._pk_get_roles()

    @api.model
    def pk_app_roles(self):
        """The roles that put a user in the app (all but ``'app': False``)."""
        return frozenset(role for role, spec in self._pk_get_roles().items() if spec['app'])

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------
    @api.model
    def pk_is_visible(self, spec, roles):
        """``include`` any-of, ``exclude`` none-of; exclude wins."""
        return pk_is_visible(spec, roles)

    @api.model
    def pk_visibility(self):
        """The declared visibility keys (read-only)."""
        return self._pk_get_visibility()

    @api.model
    def pk_can(self, key, roles, is_system=False):
        """May this role set SEE ``key``? Unknown keys raise ``KeyError``
        (typos must fail loudly, not silently hide a section).
        ``is_system`` (the viewer is in ``base.group_system``) also opens
        the keys flagged ``system``, unless one of the roles is excluded."""
        spec = self._pk_get_visibility()[key]
        if is_system and spec.get('system'):
            return not frozenset(roles or ()) & frozenset(spec.get('exclude') or ())
        return pk_is_visible(spec, roles)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    @api.model
    def pk_nav_entries(self):
        """Every declared nav entry (read-only), in declaration order."""
        return self._pk_get_nav()

    @api.model
    def pk_visible_nav(self, roles, placement, ctx=None):
        """The entries visible to ``roles`` at ``placement``, by sequence.
        ``ctx`` feeds the entries' ``requires(ctx)`` gates."""
        ctx = ctx or {}
        entries = [
            entry for entry in self._pk_get_nav()
            if placement in entry['placement']
            and pk_is_visible(entry, roles)
            and (entry.get('requires') is None or entry['requires'](ctx))
        ]
        return sorted(entries, key=lambda entry: entry['sequence'])

    @api.model
    def pk_nav_label(self, key):
        """The (lazy) label of nav entry ``key``; ``KeyError`` if unknown."""
        for entry in self._pk_get_nav():
            if entry['key'] == key:
                return entry['label']
        raise KeyError(key)

    @api.model
    def pk_nav_labels(self):
        """``{key: label}`` of every nav entry, in the current language."""
        return {entry['key']: str(entry['label']) for entry in self._pk_get_nav()}

    # ------------------------------------------------------------------
    # Pages: parent, back, crumbs, return URLs
    # ------------------------------------------------------------------
    @api.model
    def pk_pages(self):
        """``{key: Page}`` (read-only)."""
        return self._pk_get_pages()

    @api.model
    def pk_safe_return_url(self, value, fallback, prefixes=None):
        """See ``tools.pk_safe_return_url``."""
        return pk_safe_return_url(value, fallback, prefixes=prefixes)

    @api.model
    def pk_match_url(self, url):
        """``(page_key, values)`` of the registered page ``url`` points to,
        if the URL is a safe in-app path whose records the current user may
        read; else None."""
        url = pk_safe_return_url(url, None)
        if not url:
            return None
        parts = urlsplit(url)
        args = parse_qs(parts.query)
        for page in self._pk_get_pages().values():
            if not page.path or page.url is None:
                continue
            match = page.path.fullmatch(parts.path)
            if not match:
                continue
            values = page.from_url(self.env, match, args)
            if values is None:
                return None
            return page.key, values
        return None

    @api.model
    def _pk_trail(self, key, values):
        """[(label, url), …] from the top-level ancestor down to ``key``."""
        pages = self._pk_get_pages()
        trail = []
        seen = set()
        while key and key not in seen:
            seen.add(key)
            page = pages[key]
            label = str(page.label(values)) if page.label else ''
            trail.insert(0, (label, page.url(values)))
            parent = page.parent(values)
            key, values = parent if parent else (None, None)
        return trail

    @api.model
    def pk_resolve(self, key, values, request_url=None, request_return_url=None):
        """Navigation of page ``key`` rendered with ``values``.

        Returns ``{'parent_url', 'crumbs', 'context'}``: ``parent_url`` False
        on a top-level page; ``crumbs`` the ancestors, top first (the current
        page, the title, is appended by the layout); ``context`` the line
        under the title (shown with the back chevron)."""
        page = self._pk_get_pages().get(key)
        if not page:
            return {'parent_url': False, 'crumbs': [], 'context': False}
        parent = page.parent(values)
        if parent is None:
            # Top level (logo): a return URL never adds a back chevron to a tab.
            return {'parent_url': False, 'crumbs': [],
                    'context': str(page.context(values) or '') if page.context else False}
        if page.return_url is not None:
            raw_return = page.return_url(values)
        elif 'return_url' in values:
            raw_return = values.get('return_url')
        else:
            raw_return = request_return_url
        matched = self.pk_match_url(raw_return) if raw_return else None
        if matched and request_url and pk_id_key(raw_return) == pk_id_key(request_url):
            matched = None  # a page is never its own parent
        if matched:
            crumbs = self._pk_trail(*matched)
            crumbs[-1] = (crumbs[-1][0], raw_return)
        else:
            crumbs = self._pk_trail(*parent)
        context = page.context(values) if page.context else None
        return {
            'parent_url': crumbs[-1][1],
            'crumbs': crumbs,
            'context': str(context) if context else crumbs[-1][0],
        }
