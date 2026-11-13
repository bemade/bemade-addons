# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5198 (P3a): the kit scripts' markup contract takes ``pk`` names.
Task 5344 (P3b1): the shell's generic classes, style tokens and theme
attribute take ``pk`` names too.

The names the kit scripts read or write moved from ``sc`` to ``pk``:

* 32 ``data-sc-*`` attributes -> ``data-pk-*`` (``dataset.scX`` ->
  ``dataset.pkX``);
* 7 ``sc:*`` events -> ``pk:*``;
* the storage keys ``sc_draft:``, ``sc_pending_toast:v1``,
  ``sc_nav_{stack,post,up,bf_reload}:v1`` and ``sc_filters_open:``.

Task 5344 (P3b1) retires, as exact tokens:

* the 314 generic classes ``o_sc_X`` -> ``o_pk_X`` (``o_sc_chip_mauve``
  becomes ``o_pk_chip_secondary``), incl. the dynamic prefixes (``chip_``,
  ``tone_``, ``banner_``, ``tab_badge_``, ``save_state_``, ``app_body_``);
  a clinic class that merely starts like one (``o_sc_card_clock``) stays;
* the semantic and scale tokens ``--sc-<slot>`` -> ``--pk-<slot>``; the six
  Fit Crew palette tokens (``--sc-forest``, ``--sc-neon``, ``--sc-mauve``,
  ``--sc-midnight``, ``--sc-charcoal``, ``--sc-grey``) stay;
* the theme attribute ``data-sc-theme`` -> ``data-pk-theme``
  (``data-sc-theme-switch`` is a clinic name and stays).

This guard scans the kit and its consumers that are on the addons path
(views, static JS / XML / SCSS, controllers, models, tests and tours) and
fails on any retired name, with its file:line. A retired name in an addon
would be a dead hook: the kit no longer reads it. A consumer absent from
the path is skipped, so on a kit-only install only the kit is scanned.

Task 5369 (P3c1) retires the ``t-call`` names of the templates the kit
adopted: ``bemade_sports_clinic.sc_<moved>`` -> ``bemade_portal_kit.pk_<moved>``
(``tools/adopt.py``, ``ADOPTED_VIEWS``), as exact names
(``bemade_sports_clinic.sc_card_icons`` stays a clinic template).

Task 5199 (P4a) retires the save engine's and the screen refresh's
clinic names, moved to the kit under ``pk`` names:

* the attributes ``data-sc-fragment``, ``-fragment-mode``,
  ``-fragment-keep``, ``-fragment-keep-empty``, ``-keep-open`` and
  ``-rendered-at`` -> ``data-pk-*``;
* the events ``sc:saved``, ``sc:refresh``, ``sc:refresh-now`` -> ``pk:*``;
* the header ``X-Sc-Fragments`` -> ``X-Pk-Fragments``, the storage key
  ``sc_dirty_at:v1`` -> ``pk_dirty_at:v1``;
* the Python / QWeb names ``SAVE_REGISTRY`` (now the hook
  ``portal.kit._pk_save_specs()``), ``sc_fragment_key``, ``sc_now_ms``,
  ``sc_rendered_at``, ``_sc_save_json`` / ``_value`` / ``_display``,
  ``_sc_field_unchanged``, ``_sc_save_allowed``, ``sc_refresh_patterns``,
  ``sc_extract_fragments``, ``_sc_fragment_keys``, ``SC_FRAGMENTS_HEADER``
  / ``_MAX``, and the module path ``@bemade_sports_clinic/js/sc_fragments``
  (its one-release alias file names none of them).

Task 5370 (P4b) retires the form guard's, the status pills' and the lazy
edit's clinic names, moved to the kit under ``pk`` names:

* the attributes ``data-sc-guard`` and ``-guard-*`` (mode, rules, msg,
  texts, submit, reason, error, block, field-error, invalid, missing,
  generic, offline), ``-required``, ``-flash-error``, ``-error-for``,
  ``-field-error``; the pill's ``-pill-*`` and its target ``-model``,
  ``-record-id``, ``-write-date``, ``-old-value``, ``-undo-message``;
  ``-lazy-edit``, ``-lazy-edit-host``, ``-lazy-mounted``. The pill's
  ``data-sc-field`` is retired in its dataset form only (``scField``): the
  attribute stays the autosave field's, so a ``data-sc-field`` is a hit
  only on a line that names a pill too;
* the events ``sc:pill-action`` and ``sc:edit-view-open``;
* the classes ``o_sc_guard_reason`` and ``o_sc_reason_flash`` (and the
  keyframes of that name);
* the header ``X-Sc-Guard``, ``_sc_guard_probe``, the template variables
  ``sc_pill_target`` / ``sc_pill_menu_id`` and the menu id prefix
  ``sc-pill-``; the module paths ``@bemade_sports_clinic/js/sc_form_guard``,
  ``sc_status_pills``, ``sc_lazy_edit`` (their one-release alias files name
  none of them) and the interaction key
  ``bemade_sports_clinic.sc_lazy_edit``.

Task 5371 (P4c1) retires the toast's, the session notification's and the
undo's clinic names, moved to the kit under ``pk`` names:

* the attributes ``data-sc-notify``, ``-notify-title``, ``-notify-tone``,
  ``-notify-id``, ``-toast-action``, ``-toast-message``, ``-toast-tone`` and
  ``-toast-room`` (``dataset.scToast*`` too);
* the event ``sc:toast`` (``pk:toast`` only), the storage key
  ``sc_notify_shown:v1`` (read once by ``pk_toast.js`` as a fallback);
* the undo forms' old marker ``data-sc-form="<kind>.undo"`` (``sc.undo``,
  ``injury.undo``…): an undo form is ``form[data-pk-undo]`` (the session
  undo) or ``form[data-pk-undo-offer="<kind>"]``; ``data-sc-form`` itself
  stays a clinic name;
* ``_sc_pop_notification``, ``_sc_offer_undo`` and the layout value
  ``sc_notification`` (``PortalKitApp._pk_pop_notification``,
  ``_pk_offer_undo``, ``pk_notification``).

Dataset destructuring (``const { scModel, scField } = el.dataset``) is
matched too.

The one exception is the documented draft fallback of the kit
(``pk_draft_store.js`` still reads ``sc_draft:`` once, and its hoot test
checks that), and the dirty-stamp fallback of ``pk_fragments.js`` (it reads
``sc_dirty_at:v1`` once).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

from odoo.addons.bemade_portal_kit.tools.adopt import ADOPTED_VIEWS

KIT = 'bemade_portal_kit'
SCANNED_ADDONS = (KIT, 'bemade_sports_clinic', 'bemade_sports_clinic_bookings')
EXTENSIONS = ('.py', '.js', '.xml', '.scss', '.css', '.po')
SKIP_DIRS = {'__pycache__', 'node_modules', 'lib', 'description'}

ATTRIBUTES = (
    'app-shell', 'autosubmit', 'autosubmit-fallback', 'back', 'confirm',
    'confirm-ok', 'confirm-cancel', 'db', 'uid', 'display-href',
    'draft-prefix', 'edit-card', 'edit-done', 'filter-reset',
    'fragment-item', 'list-add-cancel', 'list-add-toggle', 'live-count-url',
    'live-eager', 'live-hide-zero', 'live-poll', 'live-tone-on',
    'live-tone-off', 'menu-popup', 'menu-toggle', 'section', 'submitted',
    'submitting', 'switch-off', 'switch-submit', 'user-menu-popup',
    'user-menu-toggle',
    # Task 5199 (P4a): the screen refresh.
    'fragment', 'fragment-mode', 'fragment-keep', 'fragment-keep-empty',
    'keep-open', 'rendered-at',
    # Task 5370 (P4b): the form guard, the status pills, the lazy edit.
    'guard', 'guard-mode', 'guard-rules', 'guard-msg', 'guard-texts',
    'guard-submit', 'guard-reason', 'guard-error', 'guard-block',
    'guard-field-error', 'guard-invalid', 'guard-missing', 'guard-generic',
    'guard-offline', 'required', 'flash-error', 'error-for', 'field-error',
    'pill-select', 'pill-key', 'pill-value', 'pill-post', 'pill-action',
    'pill-from', 'pill-readonly', 'pill-field', 'model', 'record-id',
    'write-date', 'old-value', 'undo-message', 'lazy-edit', 'lazy-edit-host',
    'lazy-mounted',
    # Task 5371 (P4c1): the toast, the session notification, the undo.
    'notify', 'notify-title', 'notify-tone', 'notify-id', 'toast-action',
    'toast-message', 'toast-tone', 'toast-room',
)
EVENTS = (
    'fragments', 'form-reset', 'create-success', 'lazy-loaded',
    'live-count-refresh', 'fetch-error', 'nav-sync',
    # Task 5199 (P4a).
    'saved', 'refresh', 'refresh-now',
    # Task 5370 (P4b).
    'pill-action', 'edit-view-open',
    # Task 5371 (P4c1).
    'toast',
)
STORAGE_KEYS = (
    'sc_draft:', 'sc_pending_toast:v1', 'sc_nav_stack:v1', 'sc_nav_post:v1',
    'sc_nav_up:v1', 'sc_nav_bf_reload:v1', 'sc_filters_open:',
    # Task 5199 (P4a).
    'sc_dirty_at:v1', 'X-Sc-Fragments', '@bemade_sports_clinic/js/sc_fragments',
    # Task 5370 (P4b).
    'X-Sc-Guard', '@bemade_sports_clinic/js/sc_form_guard',
    '@bemade_sports_clinic/js/sc_status_pills', '@bemade_sports_clinic/js/sc_lazy_edit',
    'bemade_sports_clinic.sc_lazy_edit',
    # Task 5371 (P4c1).
    'sc_notify_shown:v1',
)
# Task 5199 (P4a): the save engine's and the refresh's Python / QWeb names,
# as whole words.
SAVE_NAMES = (
    'SAVE_REGISTRY', 'sc_fragment_key', 'sc_now_ms', 'sc_rendered_at',
    '_sc_save_json', '_sc_save_value', '_sc_save_display',
    '_sc_field_unchanged', '_sc_save_allowed', 'sc_refresh_patterns',
    'sc_extract_fragments', '_sc_fragment_keys', 'SC_FRAGMENTS_HEADER',
    'SC_FRAGMENTS_MAX',
    # Task 5370 (P4b).
    '_sc_guard_probe', 'sc_pill_target', 'sc_pill_menu_id',
    # Task 5371 (P4c1).
    '_sc_pop_notification', '_sc_offer_undo', 'sc_notification',
)

# Task 5344 (P3b1): the generic classes, as the name after ``o_sc_``. A name
# ending in ``_`` is a prefix completed at run time (``o_sc_chip_<tone>``).
GENERIC_CLASSES = (
    'actionbar', 'actions_row', 'app', 'app_body', 'app_body_',
    'app_body_dark', 'app_body_light', 'appbar', 'appbar_action',
    'appbar_context', 'appbar_help', 'appbar_me', 'appbar_search',
    'appbar_title', 'appbar_title_text', 'autosave', 'avatar', 'back',
    'back_useful', 'banner', 'banner_', 'banner_actions', 'banner_ok',
    'banner_title', 'banner_warn', 'btn', 'btn_busy', 'btn_danger',
    'btn_ghost', 'btn_idle', 'btn_primary', 'btn_sm', 'card',
    'card_actions', 'card_archive', 'card_badge', 'card_edit', 'card_head',
    'card_icons', 'card_trash', 'check', 'chip', 'chip_', 'chip_ghost',
    'chip_green', 'chip_mauve', 'chip_orange', 'chip_red', 'chip_yellow',
    'chips', 'clear_btn', 'confirm_message', 'confirm_sheet',
    'conflict_banner', 'content', 'content_wide', 'crumb_current',
    'crumb_sep', 'crumbs', 'date_na', 'disclosure', 'disclosure_summary',
    'dot', 'draft_banner', 'dropzone', 'dropzone_input', 'dropzone_over',
    'dropzone_text', 'dropzone_text_touch', 'edit_card', 'edit_card_head',
    'edit_card_title', 'edit_done', 'edit_done_actions', 'edit_toggle_done',
    'empty', 'entity_row', 'entity_row_static', 'expand', 'expand_body',
    'field', 'field_error', 'field_history', 'field_label', 'field_message',
    'field_static', 'field_value', 'fields', 'fields_lazy', 'file',
    'file_field', 'file_field_wide', 'file_fields', 'file_head',
    'file_list', 'file_name', 'file_remove', 'file_size', 'file_too_large',
    'filter_count', 'filter_grid', 'filter_group', 'filter_group_title',
    'filters', 'filters_compact', 'footnote', 'form', 'form_actions',
    'form_actions_start', 'grid2', 'group', 'group_title', 'hint',
    'hint_link', 'history', 'history_author', 'history_body',
    'history_cleared', 'history_entry', 'history_fragment', 'history_meta',
    'history_when', 'home_picto', 'icon', 'icon_btn', 'icon_btn_danger',
    'inline_form', 'input', 'install_done', 'install_hero', 'install_icon',
    'kv', 'kv_stacked', 'lazy_body', 'lazy_loading', 'legacy', 'link',
    'link_btn', 'link_row', 'link_row_main', 'list', 'list_add',
    'list_add_cancel', 'list_add_label', 'list_add_panel', 'list_bar',
    'list_header', 'list_header_count', 'list_hint', 'logo', 'logo_mark',
    'main', 'menu_item', 'menu_popup', 'meta', 'muted', 'offline',
    'offline_main', 'offline_retry', 'page_tabs', 'page_tabs_scroll',
    'pager', 'picker', 'picker_box', 'picker_clear', 'picker_cleared',
    'picker_input', 'picker_list', 'picker_more', 'picker_native',
    'picker_none', 'picker_option', 'picker_option_active', 'pill_hint',
    'pill_option', 'pill_option_text', 'pill_popup', 'pill_select',
    'pill_select_compact', 'pill_select_wrap', 'pill_swatch', 'pill_text',
    'popup_end', 'popup_up', 'pre', 'rail', 'rail_brand', 'rail_brand_name',
    'rail_nav', 'reorder', 'row_chip_line', 'row_detail', 'row_detail_body',
    'row_expand', 'row_group', 'row_lead', 'row_lead_empty', 'row_line',
    'row_line_text', 'row_line_value', 'row_link', 'row_link_plain',
    'row_links', 'row_open', 'row_subtitle', 'row_text', 'row_title',
    'row_title_link', 'row_title_split', 'row_trailing', 'row_wrap',
    'row_wrap_reorder', 'save_state', 'save_state_', 'save_state_conflict',
    'save_state_draft', 'save_state_error', 'save_state_queued',
    'save_state_saved', 'save_state_saving', 'search', 'search_active',
    'search_add', 'search_archived', 'search_body', 'search_box',
    'search_flag', 'search_group', 'search_group_title', 'search_hint',
    'search_link', 'search_list', 'search_locked', 'search_results',
    'search_row', 'search_sheet', 'section', 'section_header',
    'section_more', 'section_sub', 'seg_input', 'segmented',
    'segmented_full', 'select', 'sheet', 'sheet_body', 'sheet_close',
    'sheet_head', 'sheet_title', 'sort', 'sort_current', 'sort_menu',
    'sort_popup', 'sort_toggle', 'spin', 'spinner', 'stat', 'stat_label',
    'stat_value', 'stats', 'status_pill', 'steps', 'switch', 'switch_card',
    'switch_control', 'switch_filter', 'switch_hint', 'switch_inline',
    'switch_input', 'switch_label', 'switch_text', 'switch_thumb',
    'switch_track', 'tab', 'tab_badge', 'tab_badge_', 'tab_badge_neutral',
    'tab_badge_red', 'tab_label', 'tab_label_long', 'tab_label_short',
    'tab_panel', 'tabs', 'tag', 'tag_remove', 'tags', 'tags_field',
    'tags_group', 'tags_option', 'tags_option_active', 'tags_options',
    'tags_search', 'textarea', 'theme_toggle', 'toast', 'toast_action',
    'toast_body', 'toast_text', 'toast_title', 'toggle_pill',
    'toggle_pill_opt', 'tone_', 'tone_green', 'tone_red', 'tone_yellow',
    'user_menu', 'user_menu_bar', 'user_menu_head', 'user_menu_item',
    'user_menu_items', 'user_menu_name', 'user_menu_popup',
    'user_menu_role', 'user_menu_who',
    # Task 5370 (P4b): the guard's reason line and its cue (and keyframes).
    'guard_reason', 'reason_flash',
)
# Semantic and scale slots of the style tokens (the palette stays ``--sc-``).
TOKEN_SLOTS = (
    'bg', 'surface', 'surface-2', 'line', 'fg', 'fg-2', 'fg-3', 'accent',
    'accent-fg', 'secondary', 'ok', 'warn', 'bad', 'overdue', 'tone-fg',
    'bar', 'bar-fg', 'bar-fg-2', 'bar-active', 'bar-active-bg', 'hover',
    'focus', 'shadow', 'font-title', 'font-text', 'text-xs', 'text-sm',
    'text-md', 'text-lg', 'title-md', 'title-lg', 'title-xl', 'space-1',
    'space-2', 'space-3', 'space-4', 'space-5', 'space-6', 'radius-sm',
    'radius-md', 'radius-lg', 'radius-pill', 'tap', 'rail-width',
    'appbar-height', 'tabs-height', 'switch-w', 'switch-h', 'switch-pad',
    'ribbon-h',
)

# The draft fallback: (path relative to the addon, retired names allowed).
ALLOWED = {
    (KIT, '__manifest__.py'): {'sc_draft:', 'sc_notify_shown:v1'},  # documents the fallbacks
    (KIT, 'static/src/js/pk_draft_store.js'): {'sc_draft:'},
    (KIT, 'static/tests/pk_draft_store.test.js'): {'sc_draft:', 'data-sc-db', 'data-sc-uid', 'o_sc_app'},
    # Task 5344: these hoot tests check that an old o_sc_app root is not read.
    (KIT, 'static/tests/pk_app_nav.test.js'): {'o_sc_app'},
    (KIT, 'tests/test_pk_retired_names.py'): None,  # this file: every name
    # Task 5199: the dirty-stamp fallback (read once) and its hoot test.
    (KIT, 'static/src/js/pk_fragments.js'): {'sc_dirty_at:v1'},
    # (and it checks that the old markers are not read any more).
    (KIT, 'static/tests/pk_fragments.test.js'): {'sc_dirty_at:v1', 'data-sc-fragment', 'data-sc-rendered-at'},
    (KIT, 'tests/test_pk_guard.py'): {'X-Sc-Guard'},  # the old header is not read
    # Task 5370: the clinic's migration that removes the old attributes from
    # the translations names them.
    ('bemade_sports_clinic', 'migrations/19.0.1.141.0/post-migrate.py'): None,
    # Task 5370: these hoot tests check that the old names are not read.
    (KIT, 'static/tests/pk_form_guard.test.js'): {'data-sc-required', 'data-sc-flash-error', 'data-sc-error-for',
                                                  'data-sc-notify', 'data-sc-notify-tone'},
    (KIT, 'static/tests/pk_status_pills.test.js'): {'sc:pill-action', 'sc:toast'},
    # Task 5371: the notification fallback (read once) and the hoot tests
    # that check the old names are not read.
    (KIT, 'static/src/js/pk_toast.js'): {'sc_notify_shown:v1'},
    (KIT, 'static/tests/pk_toast.test.js'): {
        'sc_notify_shown:v1', 'sc:toast', 'data-sc-notify', 'data-sc-notify-id', 'data-sc-toast-action',
        'data-sc-toast-message', 'data-sc-form="sc.undo"', 'data-sc-form="injury.undo"'},
    (KIT, 'static/tests/pk_lazy_edit.test.js'): {'bemade_sports_clinic.sc_lazy_edit', 'sc:edit-view-open'},
}


def _camel(name):
    head, *rest = name.split('-')
    return 'sc' + head.capitalize() + ''.join(part.capitalize() for part in rest)


def _alternation(names):
    # Longest first, so ``live-count-url`` is not read as ``live``.
    return '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))


# ``data-sc-section`` but not ``data-sc-section-title`` (a longer name that
# the kit does not read stays a consumer name).
ATTRIBUTE_RE = re.compile(r'(?<![\w])data-sc-(%s)(?![\w-])' % _alternation(ATTRIBUTES))
DATASET_RE = re.compile(
    r'''dataset(?:\.|\[\s*["'])(%s)(?![\w])''' % _alternation([_camel(a) for a in ATTRIBUTES])
)
EVENT_RE = re.compile(r'(?<![\w:-])sc:(%s)(?![\w-])' % _alternation(EVENTS))
KEY_RE = re.compile(_alternation(STORAGE_KEYS))
# Exact tokens: ``o_sc_card`` but not ``o_sc_card_clock`` (a clinic class).
CLASS_RE = re.compile(r'(?<![\w-])o_sc_(%s)(?![\w-])' % _alternation(GENERIC_CLASSES))
TOKEN_RE = re.compile(r'(?<![\w-])--sc-(%s)(?![\w-])' % _alternation(TOKEN_SLOTS))
THEME_RE = re.compile(r'(?<![\w])data-sc-theme(?![\w-])')
# Task 5369 (P3c1): the adopted templates' old full names.
ADOPTED_OLD_NAMES = tuple('%s.%s' % (module, old) for module, old, _new in ADOPTED_VIEWS)
TEMPLATE_RE = re.compile(r'(?<![\w.])(%s)(?![\w])' % _alternation(ADOPTED_OLD_NAMES))
SAVE_RE = re.compile(r'(?<![\w])(%s)(?![\w])' % _alternation(SAVE_NAMES))
# Task 5370 (P4b): dataset destructuring, ``{ scModel, scField: f } = x.dataset``.
DESTRUCTURE_RE = re.compile(r'\{([^{}]*)\}\s*=\s*[\w.$]*\.dataset\b')
DESTRUCTURED = frozenset([_camel(a) for a in ATTRIBUTES] + ['scField'])
# The pill's data-sc-field (dataset form, or the attribute on a pill line).
PILL_FIELD_RE = re.compile(r'''dataset(?:\.|\[\s*["'])scField(?![\w])''')
PILL_FIELD_ATTR_RE = re.compile(r'(?<![\w])data-sc-field(?![\w-])')
PILL_LINE_RE = re.compile(r'pill', re.IGNORECASE)
# The pill menu's old id prefix (not the tail of ``data-sc-pill-``).
PILL_ID_RE = re.compile(r'(?<![\w-])sc-pill-')
# Task 5371 (P4c1): an undo form's old marker, ``data-sc-form="<kind>.undo"``.
UNDO_FORM_RE = re.compile(r'''(?<![\w])data-sc-form=["'][\w]+\.undo["']''')


def retired_names(line):
    """The retired names found on ``line`` (as they appear)."""
    found = []
    found += [m.group(0) for m in ATTRIBUTE_RE.finditer(line)]
    found += [m.group(0) for m in DATASET_RE.finditer(line)]
    found += [m.group(0) for m in EVENT_RE.finditer(line)]
    found += [m.group(0) for m in KEY_RE.finditer(line)]
    found += [m.group(0) for m in CLASS_RE.finditer(line)]
    found += [m.group(0) for m in TOKEN_RE.finditer(line)]
    found += [m.group(0) for m in THEME_RE.finditer(line)]
    found += [m.group(0) for m in TEMPLATE_RE.finditer(line)]
    found += [m.group(0) for m in SAVE_RE.finditer(line)]
    for m in DESTRUCTURE_RE.finditer(line):
        for part in m.group(1).split(','):
            name = part.split(':')[0].strip()
            if name in DESTRUCTURED:
                found.append(name)
    found += [m.group(0) for m in PILL_FIELD_RE.finditer(line)]
    found += [m.group(0) for m in PILL_ID_RE.finditer(line)]
    found += [m.group(0) for m in UNDO_FORM_RE.finditer(line)]
    if PILL_LINE_RE.search(line):
        found += [m.group(0) for m in PILL_FIELD_ATTR_RE.finditer(line)]
    return found


def _allowed(addon, relpath, name):
    if (addon, relpath) not in ALLOWED:
        return False
    names = ALLOWED[(addon, relpath)]
    return names is None or name in names


def scan(addon, root):
    hits = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.'))
        for filename in sorted(filenames):
            if not filename.endswith(EXTENSIONS):
                continue
            path = os.path.join(dirpath, filename)
            relpath = os.path.relpath(path, root).replace(os.sep, '/')
            with open(path, encoding='utf-8', errors='replace') as f:
                for lineno, line in enumerate(f, 1):
                    for name in retired_names(line):
                        if not _allowed(addon, relpath, name):
                            hits.append(f'{addon}/{relpath}:{lineno}: {name}')
    return hits


@tagged('post_install', '-at_install')
class TestPkRetiredNames(TransactionCase):

    def test_matcher(self):
        self.assertEqual(retired_names('<div data-sc-section="notes">'), ['data-sc-section'])
        self.assertEqual(retired_names('<div data-sc-section-title="1">'), [])
        self.assertEqual(retired_names('<div data-sc-edit-card-body="1">'), [])
        self.assertEqual(retired_names('<div t-att-data-sc-live-count-url="u">'), ['data-sc-live-count-url'])
        self.assertEqual(retired_names('el.dataset.scSection'), ['dataset.scSection'])
        self.assertEqual(retired_names('el.dataset.scSectionTitle'), [])
        self.assertEqual(retired_names('ev.type === "sc:fragments"'), ['sc:fragments'])
        self.assertEqual(retired_names('"sc:fragments-done"'), [])
        self.assertEqual(retired_names('`sc:nav-sync`'), ['sc:nav-sync'])
        self.assertEqual(retired_names('get("sc_nav_bf_reload:v1")'), ['sc_nav_bf_reload:v1'])
        self.assertEqual(retired_names("'sc_filters_open': True"), [])
        self.assertEqual(retired_names('<div data-pk-section="notes"> pk:fragments pk_draft:'), [])

    def test_matcher_classes_tokens_theme(self):
        """Task 5344 (P3b1): exact tokens, the clinic names left alone."""
        self.assertEqual(retired_names('<div class="o_sc_card o_sc_card_clock">'), ['o_sc_card'])
        self.assertEqual(retired_names('.o_sc_app .o_sc_appbar_title:hover {'), ['o_sc_app', 'o_sc_appbar_title'])
        self.assertEqual(retired_names('<span class="o_sc_chip o_sc_chip_mauve">'), ['o_sc_chip', 'o_sc_chip_mauve'])
        self.assertEqual(retired_names('<span class="o_sc_chip_follow o_sc_row_contacts">'), [])
        self.assertEqual(retired_names('<span class="o_sc_reorder_row o_sc_notepad_add">'), [])
        self.assertEqual(retired_names('<span class="o_sc_reorder">'), ['o_sc_reorder'])
        self.assertEqual(retired_names('<span t-attf-class="o_sc_chip_#{tone}">'), ['o_sc_chip_'])
        self.assertEqual(retired_names("assertIn('o_sc_app_body_%s' % theme"), ['o_sc_app_body_'])
        self.assertEqual(retired_names("cls.split('o_sc_chip_')[1]"), ['o_sc_chip_'])
        self.assertEqual(retired_names('el.classList.toggle(`o_sc_chip_${on}`)'), ['o_sc_chip_'])
        self.assertEqual(retired_names("'o_sc_med_%s' % tone, 'o_sc_dash_zone_x'"), [])
        self.assertEqual(retired_names('animation: o_sc_spin 1s linear infinite;'), ['o_sc_spin'])
        self.assertEqual(retired_names('color: var(--sc-accent-fg, var(--sc-fg));'), ['--sc-accent-fg', '--sc-fg'])
        self.assertEqual(retired_names('--sc-bar-fg-2: #fff; --sc-surface-2: #000;'), ['--sc-bar-fg-2', '--sc-surface-2'])
        self.assertEqual(retired_names('style.setProperty("--sc-ribbon-h", h)'), ['--sc-ribbon-h'])
        self.assertEqual(
            retired_names('var(--sc-forest) var(--sc-neon) var(--sc-mauve) var(--sc-midnight) '
                          'var(--sc-charcoal) var(--sc-grey)'), [])
        self.assertEqual(retired_names('<div data-sc-theme="dark">'), ['data-sc-theme'])
        self.assertEqual(retired_names('<div t-att-data-sc-theme="t">'), ['data-sc-theme'])
        self.assertEqual(retired_names('<input data-sc-theme-switch="1"/>'), [])
        self.assertEqual(retired_names('@mixin sc-theme-dark {'), [])
        self.assertEqual(
            retired_names('<div class="o_pk_app o_pk_chip_secondary" data-pk-theme="light" '
                          'style="color: var(--pk-accent)">'), [])

    def test_matcher_adopted_templates(self):
        """Task 5369 (P3c1): the adopted templates' old names, exact."""
        self.assertEqual(retired_names('<t t-call="bemade_sports_clinic.sc_icon">'), ['bemade_sports_clinic.sc_icon'])
        self.assertEqual(retired_names('t-call="bemade_sports_clinic.sc_card"'), ['bemade_sports_clinic.sc_card'])
        self.assertEqual(retired_names('t-call="bemade_sports_clinic.sc_card_icons"'), [])
        self.assertEqual(retired_names('t-call="bemade_sports_clinic.sc_empty_state_x"'), [])
        self.assertEqual(retired_names("env.ref('bemade_sports_clinic.sc_frontend_layout')"),
                         ['bemade_sports_clinic.sc_frontend_layout'])
        self.assertEqual(retired_names('arch_db:bemade_sports_clinic.sc_list_add_cancel'),
                         ['bemade_sports_clinic.sc_list_add_cancel'])
        self.assertEqual(retired_names('t-call="bemade_portal_kit.pk_icon" sc_card'), [])

    def test_matcher_save_engine(self):
        """Task 5199 (P4a): the save engine and screen refresh names."""
        self.assertEqual(retired_names('<div t-att-data-sc-fragment="sc_fragment_key(p, \'hero\')">'),
                         ['data-sc-fragment', 'sc_fragment_key'])
        self.assertEqual(retired_names('<ul data-sc-fragment-mode="list" data-sc-fragment-keep-empty="1">'),
                         ['data-sc-fragment-mode', 'data-sc-fragment-keep-empty'])
        self.assertEqual(retired_names('el.dataset.scFragment; el.dataset.scFragmentKeep; root.dataset.scRenderedAt'),
                         ['dataset.scFragment', 'dataset.scFragmentKeep', 'dataset.scRenderedAt'])
        self.assertEqual(retired_names('<details data-sc-keep-open="x">'), ['data-sc-keep-open'])
        self.assertEqual(retired_names('"sc:saved" "sc:refresh" "sc:refresh-now"'),
                         ['sc:saved', 'sc:refresh', 'sc:refresh-now'])
        self.assertEqual(retired_names("headers={'X-Sc-Fragments': k}"), ['X-Sc-Fragments'])
        self.assertEqual(retired_names('import { x } from "@bemade_sports_clinic/js/sc_fragments";'),
                         ['@bemade_sports_clinic/js/sc_fragments'])
        self.assertEqual(retired_names('self._sc_save_json(p) or sc_now_ms() or SAVE_REGISTRY'),
                         ['_sc_save_json', 'sc_now_ms', 'SAVE_REGISTRY'])
        self.assertEqual(retired_names('_pk_save_json pk_now_ms pk_fragment_key data-pk-fragment pk:saved'), [])
        self.assertEqual(retired_names('_sc_save_proposal sc_fragments_1611 data-sc-edit-open'), [])

    def test_matcher_guard_pills_lazy(self):
        """Task 5370 (P4b): the guard, pills and lazy edit names."""
        self.assertEqual(retired_names('<form data-sc-guard="1" data-sc-guard-mode="fetch">'),
                         ['data-sc-guard', 'data-sc-guard-mode'])
        self.assertEqual(retired_names('<p data-sc-flash-error="1"/><p data-sc-error-for="x"/>'),
                         ['data-sc-flash-error', 'data-sc-error-for'])
        self.assertEqual(retired_names('el.dataset.scGuardBlock; form.dataset.scGuardMode'),
                         ['dataset.scGuardBlock', 'dataset.scGuardMode'])
        self.assertEqual(retired_names('const { scModel, scRecordId: id, scField } = pill.dataset;'),
                         ['scModel', 'scRecordId', 'scField'])
        self.assertEqual(retired_names('const { scState } = el.dataset;'), [])
        self.assertEqual(retired_names('el.dataset.scField === f'), ['dataset.scField'])
        self.assertEqual(retired_names("tree.xpath('//*[@data-sc-pill-select][@data-sc-field=\"x\"]')"),
                         ['data-sc-pill-select', 'data-sc-field'])
        # The autosave field's data-sc-field stays.
        self.assertEqual(retired_names('.o_pk_autosave[data-sc-field="name"]'), [])
        self.assertEqual(retired_names('"sc:pill-action" "sc:edit-view-open" sc:toast'),
                         ['sc:pill-action', 'sc:edit-view-open', 'sc:toast'])
        self.assertEqual(retired_names('class="o_sc_guard_reason o_sc_reason_flash"'),
                         ['o_sc_guard_reason', 'o_sc_reason_flash'])
        self.assertEqual(retired_names("headers={'X-Sc-Guard': '1'} _sc_guard_probe()"),
                         ['X-Sc-Guard', '_sc_guard_probe'])
        self.assertEqual(retired_names('t-call="bemade_sports_clinic.sc_form_guard_slots"'),
                         ['bemade_sports_clinic.sc_form_guard_slots'])
        self.assertEqual(retired_names('t-call="bemade_sports_clinic.sc_status_pill_select"'),
                         ['bemade_sports_clinic.sc_status_pill_select'])
        self.assertEqual(retired_names('from "@bemade_sports_clinic/js/sc_form_guard";'),
                         ['@bemade_sports_clinic/js/sc_form_guard'])
        self.assertEqual(retired_names('<template data-sc-lazy-edit="1"/> data-sc-lazy-url data-sc-form'),
                         ['data-sc-lazy-edit'])
        self.assertEqual(retired_names("'sc-pill-%s' % key"), ['sc-pill-'])
        self.assertEqual(retired_names('data-pk-guard data-pk-pill-select pk:pill-action o_pk_guard_reason'), [])

    def test_matcher_toast_undo(self):
        """Task 5371 (P4c1): the toast, notification and undo names."""
        self.assertEqual(retired_names('<div t-att-data-sc-notify="m" t-att-data-sc-notify-id="i">'),
                         ['data-sc-notify', 'data-sc-notify-id'])
        self.assertEqual(retired_names('toast.dataset.scNotifyTone; button.dataset.scToastAction = "1"'),
                         ['dataset.scNotifyTone', 'dataset.scToastAction'])
        self.assertEqual(retired_names('document.body.dataset.scToastRoom; t.dataset.scToastTone'),
                         ['dataset.scToastRoom', 'dataset.scToastTone'])
        self.assertEqual(retired_names('new CustomEvent("sc:toast", { detail })'), ['sc:toast'])
        self.assertEqual(retired_names('"sc:toaster" pk:toast'), [])
        self.assertEqual(retired_names('getItem("sc_notify_shown:v1")'), ['sc_notify_shown:v1'])
        self.assertEqual(retired_names('<form data-sc-form="sc.undo" t-att-data-sc-toast-action="l">'),
                         ['data-sc-toast-action', 'data-sc-form="sc.undo"'])
        self.assertEqual(retired_names("xpath('//form[@data-sc-form=\"injury.undo\"]')"),
                         ['data-sc-form="injury.undo"'])
        self.assertEqual(retired_names('<form data-sc-form="team.player.add" data-sc-form="note">'), [])
        self.assertEqual(retired_names("'sc_notification': self._sc_pop_notification(); self._sc_offer_undo(m, u)"),
                         ['sc_notification', '_sc_pop_notification', '_sc_offer_undo'])
        self.assertEqual(retired_names('sc_notification_x _sc_offer_undo_x'), [])
        self.assertEqual(retired_names('pk_notification data-pk-notify data-pk-undo-offer="injury" pk_notify_shown:v1'),
                         [])

    def test_no_retired_name_left(self):
        hits = []
        for addon in SCANNED_ADDONS:
            root = get_module_path(addon, display_warning=False)
            if root:
                hits += scan(addon, root)
        self.assertFalse(hits, 'retired sc names (tasks 5198 / 5344, use the pk names):\n' + '\n'.join(hits))
