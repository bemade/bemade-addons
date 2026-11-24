# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5199 (P4a): read fragments, the screen refresh after a save.

A server-built, READ-ONLY region of an app page carries
``data-pk-fragment="<key>"`` (``pk_fragment_key(record, part)`` in the
templates gives ``<model>:<id>:<part>``; page-level regions use
``page:<name>:<part>``). Keys are unique on the page and stable across
renders. A region never holds an OWL island (``owl-component``): mark its
read-only parts instead.

* A save answers ``refresh``: the key patterns of its spec's ``refresh`` map
  resolved for the record (``pk_refresh_patterns``), where ``*`` matches
  within one key segment.
* The page (``@bemade_portal_kit/js/pk_fragments``) matches them against the
  keys it carries and GETs ITS OWN URL with the ``X-Pk-Fragments: k1,k2``
  header: the page route renders exactly as for a reload (same values, same
  access rules, same QWeb) and answers only those nodes as JSON
  (``PortalKitApp._pk_fragments_response``):
  ``{fragments: {key: outer html}, missing: [...], title, rendered_at}``.
* The client swaps each node in place (see the script for the rules:
  ``data-pk-fragment-mode="list"``, ``-fragment-keep``,
  ``-fragment-keep-empty``, ``data-pk-keep-open``).
* The shell root carries ``data-pk-rendered-at`` (server ms): a page shown
  again by « back » reloads when something was saved after it was rendered.
"""
import re
import time

from lxml import etree
from lxml import html as lxml_html

PK_FRAGMENTS_HEADER = 'X-Pk-Fragments'
PK_FRAGMENTS_MAX = 200
_KEY_RE = re.compile(r'^[\w.\-]+(?::[\w.\-*]+)*$')


def pk_fragment_key(record, part):
    """The fragment key of ``part`` of ``record`` (``<model>:<id>:<part>``)."""
    return '%s:%s:%s' % (record._name, record.id, part)


def pk_now_ms():
    """Server time in ms (the render stamp and a save's ``saved_at``: both on
    the server clock, so the « back » check never compares two clocks)."""
    return int(time.time() * 1000)


def pk_parse_fragment_keys(raw):
    """The keys of an ``X-Pk-Fragments`` header value, or None without one:
    stripped, de-duplicated, malformed keys dropped, at most
    ``PK_FRAGMENTS_MAX``."""
    if raw is None:
        return None
    keys = []
    for key in raw.split(','):
        key = key.strip()
        if key and _KEY_RE.match(key) and key not in keys:
            keys.append(key)
    return keys[:PK_FRAGMENTS_MAX]


def pk_extract_fragments(html, keys):
    """``({key: outer html}, title)``: the first node of the rendered page
    ``html`` carrying each of ``keys`` in ``data-pk-fragment``, and the
    document title."""
    tree = lxml_html.document_fromstring(html)
    wanted = set(keys)
    found = {}
    for node in tree.iterfind('.//*[@data-pk-fragment]'):
        key = node.get('data-pk-fragment')
        if key in wanted and key not in found:
            found[key] = etree.tostring(node, encoding='unicode', method='html', with_tail=False)
    title = tree.find('.//title')
    return found, (title.text_content().strip() if title is not None else '')


def pk_refresh_patterns(spec, record, field):
    """The fragment key patterns a save of ``record.field`` makes stale,
    from the save spec's ``refresh`` map: ``{field | '*': [entry, ...]}``.
    An entry is a part of THIS record's keys (``'hero'`` ->
    ``<model>:<id>:hero``, ``'*'`` = all of them), a full key pattern, or
    ``callable(record) -> [patterns]`` (another record's keys; called with
    the record as sudo)."""
    refresh = (spec or {}).get('refresh') or {}
    base = '%s:%s' % (record._name, record.id)
    patterns = []
    for entry in tuple(refresh.get('*', ())) + tuple(refresh.get(field, ())):
        items = entry(record.sudo()) if callable(entry) else (entry,)
        for item in items or ():
            if not item:
                continue
            if ':' not in item:
                item = '%s:%s' % (base, item)
            if item not in patterns:
                patterns.append(item)
    return patterns
