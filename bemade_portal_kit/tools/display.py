# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5381 (kit P4c2): the render helpers of a card's read view.

Pure functions, no state. A consumer passes them to its templates (its
page values) under these names; the kit's templates
(``pk_display_row``) call them:

* ``pk_display(record, field)``: the value as a reader sees it (a name for
  a many2one, a label for a selection, a formatted date; '' when empty). The
  save route answers the same string (``PortalKitApp._pk_save_display``),
  so a read view updated in place after a save matches a reload. A model's
  save spec may shape it (``display``);
* ``pk_display_key(record, field)``: ``model:id:field``, the key of the
  read views a save refreshes (``data-pk-display``);
* ``pk_contact_href(kind, value)``: the tap-to-call / tap-to-email href of
  a shown phone or email (``kind`` = ``'tel'`` / ``'mailto'``), or None
  when there is nothing to dial or write to. A phone keeps only ``+`` and
  its digits. Same rule in the browser: ``static/src/js/pk_contact_href.js``.
"""
import re

from odoo.tools import format_date, format_datetime

from .registry import pk_freeze


def pk_display(record, field):
    """``record.field`` as a reader sees it ('' when empty)."""
    spec = record.env['portal.kit'].pk_save_spec(record._name) or pk_freeze({})
    if spec.get('display'):
        shown = spec['display'](record, field)
        if shown is not None:
            return shown
    definition = record._fields.get(field)
    if definition is None:
        return ''
    value = record[field]
    if not value:
        return ''
    if definition.type == 'many2one':
        # The plain name, as the select options show it.
        value = value.sudo()
        return (value.name if 'name' in value._fields else value.display_name) or ''
    if definition.type == 'selection':
        return dict(definition._description_selection(record.env)).get(value, '')
    if definition.type == 'date':
        return format_date(record.env, value)
    if definition.type == 'datetime':
        return format_datetime(record.env, value)
    return str(value)


def pk_display_key(record, field):
    """The key of ``record.field``'s read views: ``model:id:field``."""
    return '%s:%s:%s' % (record._name, record.id, field)


def pk_contact_href(kind, value):
    """``tel:`` / ``mailto:`` href of a shown phone / email, or None."""
    value = (value or '').strip() if isinstance(value, str) else ''
    if not value:
        return None
    if kind == 'tel':
        digits = re.sub(r'[^0-9+]', '', value)
        return 'tel:%s' % digits if re.search(r'[0-9]', digits) else None
    if kind == 'mailto':
        return 'mailto:%s' % value
    return None
