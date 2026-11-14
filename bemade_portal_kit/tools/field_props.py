# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5382 (kit P4c3): the props of the autosave field.

Pure functions, no state. Each builder returns the JSON ``props`` of the
kit's component ``bemade_portal_kit.pk_autosave_field``, for the kit's
template::

    <t t-call="bemade_portal_kit.pk_field_autosave">
        <t t-set="props" t-value="pk_field_props(record, 'name', label)"/>
    </t>

A consumer passes them to its templates (its page values) under these
names:

* ``pk_field_props(record, field, label, input_type='text', **extra)``: a
  SERVER-mode field of ``record.field`` (the value and write date the save
  route ``/my/app/save/<model>/<id>`` compares against); input id
  ``pk_<model>_<id>_<field>``;
* ``pk_draft_props(draft_key, name, label, input_type='text', value='',
  **extra)``: a DRAFT-mode field, a real form field (``name``) whose typing
  is kept on the device under ``draft_key``. The key is the caller's,
  verbatim: a consumer never changes it, or the drafts its users kept on
  their devices are lost. Input id ``pk_draft_<name>``;
* ``pk_form_props(target, label, input_type='tags', value='', **extra)``: a
  FORM-mode field, written to the enclosing form's hidden input ``target``
  (its id); input id ``<target>_field``;
* ``pk_options(pairs)``: ``[(key, label[, group label, group key])]`` ->
  JSON-safe ``[[str, ...]]``.

``extra``: any of the component's props (``options``, ``placeholder``,
``hint``, ``clearable``, ``instant``, ``undoMessage``, ``replace`` and its
labels, ``groupSelect`` and its texts, ``picker``, ``pickerKey``,
``optionMeta``, ``savedLabel``, ``inputId``…). ``None`` is left out; the
texts become strings (a lazy translation is rendered now).
"""
import json

from odoo import fields

from .save import pk_save_value

# The props that are texts (rendered to str: a lazy translation).
TEXT_PROPS = frozenset((
    'hint', 'placeholder', 'undoMessage', 'historyLabel', 'savedLabel',
    'replaceCurrentLabel', 'replaceNewLabel', 'replaceReuseLabel',
    'groupConfirmMessage', 'groupConfirmLabel', 'groupNotice',
))


def pk_options(pairs):
    """``[(key, label, …)]`` -> JSON-safe ``[[str(key), str(label), …]]``."""
    return [[str(part) for part in option] for option in pairs]


def _props(props, extra):
    if extra.get('options') is not None:
        extra = dict(extra, options=pk_options(extra['options']))
    for key, value in extra.items():
        if value is not None:
            props[key] = str(value) if key in TEXT_PROPS else value
    return json.dumps(props, default=str)


def pk_field_props(record, field, label, input_type='text', **extra):
    """The JSON props of a SERVER-mode autosave field of ``record.field``."""
    props = {
        'mode': 'server',
        'model': record._name,
        'recordId': record.id,
        'field': field,
        'writeDate': fields.Datetime.to_string(record.write_date),
        'label': str(label),
        'inputType': input_type,
        'inputId': 'pk_%s_%s_%s' % (record._name.replace('.', '_'), record.id, field),
        'value': pk_save_value(record, field),
    }
    return _props(props, extra)


def pk_draft_props(draft_key, name, label, input_type='text', value='', **extra):
    """The JSON props of a DRAFT-mode autosave field (``draft_key``: the
    caller's device draft key, verbatim)."""
    props = {
        'mode': 'draft',
        'name': name,
        'draftKey': draft_key,
        'label': str(label),
        'inputType': input_type,
        'inputId': 'pk_draft_%s' % name,
        'value': value or '',
    }
    return _props(props, extra)


def pk_form_props(target, label, input_type='tags', value='', **extra):
    """The JSON props of a FORM-mode autosave field: no save, no draft; the
    value goes to the enclosing form's hidden input ``target`` (its id)."""
    props = {
        'mode': 'form',
        'target': target,
        'label': str(label),
        'inputType': input_type,
        'inputId': '%s_field' % target,
        'value': value or '',
    }
    return _props(props, extra)
