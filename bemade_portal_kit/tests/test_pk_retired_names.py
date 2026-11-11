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

The one exception is the documented draft fallback of the kit
(``pk_draft_store.js`` still reads ``sc_draft:`` once, and its hoot test
checks that).
"""
import os
import re

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

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
)
EVENTS = (
    'fragments', 'form-reset', 'create-success', 'lazy-loaded',
    'live-count-refresh', 'fetch-error', 'nav-sync',
)
STORAGE_KEYS = (
    'sc_draft:', 'sc_pending_toast:v1', 'sc_nav_stack:v1', 'sc_nav_post:v1',
    'sc_nav_up:v1', 'sc_nav_bf_reload:v1', 'sc_filters_open:',
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
    'user_menu_role', 'user_menu_who'
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
    (KIT, '__manifest__.py'): {'sc_draft:'},  # documents the fallback
    (KIT, 'static/src/js/pk_draft_store.js'): {'sc_draft:'},
    (KIT, 'static/tests/pk_draft_store.test.js'): {'sc_draft:', 'data-sc-db', 'data-sc-uid', 'o_sc_app'},
    # Task 5344: these hoot tests check that an old o_sc_app root is not read.
    (KIT, 'static/tests/pk_app_nav.test.js'): {'o_sc_app'},
    (KIT, 'tests/test_pk_retired_names.py'): None,  # this file: every name
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

    def test_no_retired_name_left(self):
        hits = []
        for addon in SCANNED_ADDONS:
            root = get_module_path(addon, display_warning=False)
            if root:
                hits += scan(addon, root)
        self.assertFalse(hits, 'retired sc names (tasks 5198 / 5344, use the pk names):\n' + '\n'.join(hits))
