# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Pure helpers of the ``portal.kit`` registries (no ORM state, no module
state). Moved from ``bemade_sports_clinic/models/sc_app_roles.py`` and
``models/sc_app_nav.py`` (task 5196).

* ``pk_nav(...)``          a nav entry (hook ``_pk_nav``);
* ``Page`` / ``pk_static_page``  a page (hook ``_pk_pages``);
* ``pk_is_visible``        the include / exclude rule of every registry;
* ``pk_safe_return_url``   the ONE return-URL validator;
* ``pk_readable`` / ``pk_arg`` / ``pk_int``  helpers for a page's
  ``from_url`` (rebuild its values from a URL, as the current user).
"""
import re
from types import MappingProxyType
from urllib.parse import parse_qs, urlsplit

from odoo.exceptions import AccessError, MissingError


# ---------------------------------------------------------------------------
# Visibility rule
# ---------------------------------------------------------------------------


def pk_is_visible(spec, roles):
    """``include`` any-of, ``exclude`` none-of; exclude wins."""
    roles = frozenset(roles or ())
    if roles & frozenset(spec.get('exclude') or ()):
        return False
    return bool(roles & frozenset(spec.get('include') or ()))


# ---------------------------------------------------------------------------
# Nav entries
# ---------------------------------------------------------------------------


def pk_nav(key, label, icon, url, include, sequence, placement,
           exclude=(), requires=None, subtitle=None):
    """A nav entry. ``placement``: where it shows (e.g. ``('tab', 'rail')``);
    ``requires``: an optional ``callable(ctx) -> bool`` feature gate."""
    return {
        'key': key, 'label': label, 'icon': icon, 'url': url,
        'include': frozenset(include), 'exclude': frozenset(exclude),
        'requires': requires, 'placement': tuple(placement),
        'sequence': sequence, 'subtitle': subtitle,
    }


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


class Page:
    """One page of the shell.

    * ``parent(v)``  -> ``(parent_key, parent_values)`` or ``None`` (top level);
      ``v`` is the page's render values.
    * ``url(v)``     the page's canonical URL (needed for an ancestor page).
    * ``label(v)``   its crumb label (a string or a callable).
    * ``context(v)`` optional: the line under the title (default: the
      immediate parent's label).
    * ``path`` + ``from_url(env, match, args)``: the URL pattern
      (fullmatched against a return URL's path) and how to rebuild the
      page's values from it, as the current user (``None`` = refused).
      Together they are the return-URL allowlist.
    * ``return_url(v)``: optional, the page's « came from » URL (default
      ``v['return_url']``, else the request's ``?return_url=``).
    """
    __slots__ = ('key', 'parent', 'has_parent', 'url', 'label', 'context', 'path',
                 'from_url', 'return_url')

    def __init__(self, key, *, parent=None, url=None, label=None, context=None,
                 path=None, from_url=None, return_url=None):
        self.key = key
        self.has_parent = parent is not None
        self.parent = parent or (lambda v: None)
        self.url = url if callable(url) or url is None else (lambda v, _u=url: _u)
        self.label = label if callable(label) or label is None else (lambda v, _l=label: _l)
        self.context = context
        self.path = re.compile(path) if path else None
        self.from_url = from_url or (lambda env, match, args: {})
        self.return_url = return_url

    def __repr__(self):
        return '<Page %s>' % self.key


def pk_static_page(key, url, label, parent=None, path=None):
    """A page with a fixed URL (its path defaults to the URL itself)."""
    return Page(key, url=url, label=label, parent=parent,
                path=path or re.escape(url))


# ---------------------------------------------------------------------------
# Return URLs
# ---------------------------------------------------------------------------


def pk_safe_return_url(value, fallback, prefixes=None):
    """``value`` if it is a same-site relative path, else ``fallback`` (no
    open redirect through a posted ``return_url``).

    Accepted: ``/…`` only. Refused: empty / non-string, a scheme
    (``https://…``, ``javascript:…``), protocol-relative ``//…``, any
    backslash (browsers read ``/\\evil`` as ``//evil``), and any control
    character (browsers drop tab/newline, so ``/<TAB>/evil`` would become
    ``//evil``). A plain space is allowed (search-filter return URLs).
    ``prefixes`` (optional tuple) further restricts the accepted paths."""
    if not value or not isinstance(value, str):
        return fallback
    if (not value.startswith('/') or value.startswith('//')
            or '\\' in value
            or any(ord(ch) < 0x20 or ord(ch) == 0x7f for ch in value)):
        return fallback
    if prefixes and not value.startswith(tuple(prefixes)):
        return fallback
    return value


def pk_id_key(url):
    """A URL's identity: its path + the ``*id`` query args (the view state —
    tab, filters, flash messages — is not part of « which page »)."""
    parts = urlsplit(url or '')
    args = sorted((k, v) for k, vs in parse_qs(parts.query).items()
                  for v in vs if k.endswith('id'))
    return parts.path, tuple(args)


# ---------------------------------------------------------------------------
# from_url helpers
# ---------------------------------------------------------------------------


def pk_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def pk_arg(args, key):
    """The first value of ``key`` in parsed query ``args`` (``parse_qs``)."""
    values = args.get(key) or []
    return values[0] if values else None


def pk_readable(env, model, raw_id):
    """``env[model]`` record ``raw_id`` if the CURRENT user may read it, else
    None (a return URL never reveals a record the user cannot open)."""
    rid = pk_int(raw_id)
    if not rid:
        return None
    record = env[model].browse(rid)
    try:
        if not record.exists():
            return None
        record.check_access('read')
    except (AccessError, MissingError):
        return None
    return record


# ---------------------------------------------------------------------------
# Freezing (the cached registries are shared by every request of a database)
# ---------------------------------------------------------------------------


def pk_freeze(mapping):
    """A read-only view of a copy of ``mapping``."""
    return MappingProxyType(dict(mapping))
