# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
"""Task 5345 (kit P3c2): the shell components the kit adopted.

Each renders with the kit alone (no consumer template, class or
attribute), with ``pk`` names:

* UC-C1 ``pk_list_header``: « Add » as a link, a sheet opener or a panel
  toggle (``data-pk-action`` = ``add_key``), the count, the sort menu
  (``data-pk-sort``, the active one checked, its label shown).
* UC-C2 ``pk_card_icons``: the body, the ``ci_extra`` slot, the activity
  clock (``o_pk_card_clock``, ``data-pk-activity-clock`` /
  ``-activity-overdue``, the overdue class, hidden at 0 unless ``always``),
  archive (inline form / sheet / outside form), trash (gated by the edit
  mode unless ``always``), the pencil; in that order.
* UC-C3 ``pk_history_entry`` / ``pk_history_list``: meta line, body or
  « Cleared », ``data-pk-history-state``, ``data-pk-scope``; the empty
  message.
* UC-C4 ``pk_banner`` and ``pk_flash_banners`` (reads ``pk_flash``).
* UC-C5 ``pk_switch``: locked (``data-pk-switch-locked``) with its reason
  (``data-pk-switch-reason``, ``o_pk_switch_reason``), the off twin.
* UC-C6 ``pk_confirm_sheet``: a pk_sheet with one POST form,
  ``data-pk-confirm-submit``.
* UC-C7 ``pk_link_row`` and ``pk_row_links``: the stretched main link, a
  split title (``data-pk-title-split``, ``-title-link``), the secondary
  links (``data-pk-row-links``, ``-row-link``, ``-row-link-plain``).
* UC-C8 ``pk_entity_row`` (``row_extra`` slot), ``pk_field_static`` and
  ``pk_overdue_flag`` (``o_pk_overdue``, ``data-pk-overdue``).
Synthetic data only.
"""
import re
from unittest.mock import MagicMock

from lxml import html as lxml_html

from odoo.tests import TransactionCase, tagged

KIT = 'bemade_portal_kit'
CONSUMER_RE = re.compile(r'data-sc-|o_sc_|\bsc_|bemade_sports_clinic')


@tagged('post_install', '-at_install')
class TestPkComponents(TransactionCase):

    def _render(self, name, values=None, body='', slots=None):
        slots = ''.join('<t t-set="%s">%s</t>' % item for item in (slots or {}).items())
        arch = '<t t-name="pk_t_call"><t t-call="%s.%s">%s%s</t></t>' % (KIT, name, slots, body)
        view = self.env['ir.ui.view'].create({'name': 'pk_t_call', 'type': 'qweb', 'arch': arch})
        fake = MagicMock()
        fake.csrf_token.return_value = 'pk-t-token'
        out = self.env['ir.qweb'].with_context(minimal_qcontext=True)._render(
            view.id, dict(values or {}, request=fake))
        root = lxml_html.fragment_fromstring(str(out), create_parent='div')
        self.assertNotRegex(lxml_html.tostring(root, encoding='unicode'), CONSUMER_RE)
        return root

    # ------------------------------------------------------------- UC-C1
    def test_list_header(self):
        self.assertEqual(len(self._render('pk_list_header')), 0)
        sorts = [{'key': 'name', 'label': 'Name', 'url': '/pk/t?sort=name', 'active': False},
                 {'key': 'date', 'label': 'Date', 'url': '/pk/t?sort=date', 'active': True}]
        root = self._render('pk_list_header', {
            'add_label': 'Add an item', 'add_url': '/pk/t/new', 'add_key': 'items.add', 'count': '2 items',
            'sorts': sorts, 'sort_id': 'pk_t_sort', 'sort_label': 'Sort items', 'header_section': 'items.head',
        })
        head = root.xpath('./div[contains(@class, "o_pk_list_header")]')[0]
        self.assertEqual(head.get('data-pk-section'), 'items.head')
        add = head.xpath('./a[contains(@class, "o_pk_list_add")]')[0]
        self.assertEqual((add.get('href'), add.get('data-pk-action'), add.get('aria-label')),
                         ('/pk/t/new', 'items.add', 'Add an item'))
        self.assertEqual(add.xpath('.//span/text()'), ['Add'])
        self.assertEqual(head.xpath('.//span[contains(@class, "o_pk_list_header_count")]/text()'), ['2 items'])
        links = head.xpath('.//div[@id="pk_t_sort"]//a')
        self.assertEqual([a.get('data-pk-sort') for a in links], ['name', 'date'])
        self.assertEqual([a.get('aria-checked') for a in links], ['false', 'true'])
        self.assertEqual(head.xpath('.//span[@class="o_pk_sort_current"]/text()'), ['Date'])
        root = self._render('pk_list_header', {'add_label': 'Add', 'add_sheet': 'pk_t_sheet', 'add_key': 'k'})
        self.assertEqual(root.xpath('.//button/@data-pk-sheet-open'), ['pk_t_sheet'])
        root = self._render('pk_list_header', {'add_label': 'Add', 'add_panel': 'pk_t_panel', 'add_open': True})
        button = root.xpath('.//button[@data-pk-list-add-toggle]')[0]
        self.assertEqual((button.get('aria-controls'), button.get('aria-expanded')), ('pk_t_panel', 'true'))
        self.assertIsNone(button.get('data-pk-action'))

    # ------------------------------------------------------------- UC-C2
    def test_card_icons(self):
        root = self._render('pk_card_icons', {
            'ci_clock': {'count': 3, 'overdue': 1, 'url': '/pk/t/activities', 'key': 'items.activities'},
            'ci_archive': {'action': '/pk/t/archive', 'hidden': {'return_url': '/pk/t'}, 'key': 'items.archive',
                           'section': 'items.archive'},
            'ci_trash': {'sheet': 'pk_t_delete', 'key': 'items.delete'},
            'ci_editable': True, 'ci_edit_key': 'items.edit', 'ci_edit_for': 'pk_t_card',
        }, body='<span class="pk_t_chip">chip</span>', slots={'ci_extra': '<button class="pk_t_star">*</button>'})
        icons = root.xpath('./span[@data-pk-card-icons="1"]')[0]
        order = []
        for el in icons:
            classes = el.get('class') or ''
            for name in ('pk_t_chip', 'pk_t_star', 'o_pk_card_clock', 'o_pk_inline_form', 'o_pk_card_trash',
                         'o_pk_card_edit'):
                if name in classes.split():
                    order.append(name)
        self.assertEqual(order, ['pk_t_chip', 'pk_t_star', 'o_pk_card_clock', 'o_pk_inline_form', 'o_pk_card_trash',
                                 'o_pk_card_edit'])
        clock = icons.xpath('./a[contains(@class, "o_pk_card_clock")]')[0]
        self.assertIn('o_pk_card_clock_overdue', clock.get('class'))
        self.assertEqual((clock.get('href'), clock.get('data-pk-activity-clock'), clock.get('data-pk-activity-overdue'),
                          clock.get('data-pk-action'), clock.get('aria-label')),
                         ('/pk/t/activities', '3', '1', 'items.activities', 'Activities'))
        archive = icons.xpath('./form')[0]
        self.assertEqual((archive.get('action'), archive.get('data-pk-section')), ('/pk/t/archive', 'items.archive'))
        self.assertEqual(archive.xpath('.//input[@name="return_url"]/@value'), ['/pk/t'])
        button = archive.xpath('.//button[@data-pk-card-archive="1"]')[0]
        self.assertEqual((button.get('data-pk-action'), button.get('aria-label')), ('items.archive', 'Archive'))
        trash = icons.xpath('./button[@data-pk-card-trash="1"]')[0]
        self.assertEqual((trash.get('data-pk-sheet-open'), trash.get('data-pk-action'), trash.get('aria-label')),
                         ('pk_t_delete', 'items.delete', 'Delete'))
        self.assertEqual((trash.get('data-pk-edit-only'), trash.get('data-pk-edit-for'), trash.get('hidden')),
                         ('1', 'pk_t_card', 'hidden'))
        edit = icons.xpath('./button[@data-pk-edit-toggle="1"]')[0]
        self.assertEqual((edit.get('data-pk-action'), edit.get('data-pk-edit-for'), edit.get('aria-label')),
                         ('items.edit', 'pk_t_card', 'Edit'))

    def test_card_icons_variants(self):
        # No activity: no clock, unless « always » (then no badge).
        root = self._render('pk_card_icons', {'ci_clock': {'count': 0, 'url': '/x'}})
        self.assertFalse(root.xpath('.//a[contains(@class, "o_pk_card_clock")]'))
        root = self._render('pk_card_icons', {'ci_clock': {'count': 0, 'url': '/x', 'always': True}})
        clock = root.xpath('.//a[contains(@class, "o_pk_card_clock")]')[0]
        self.assertNotIn('o_pk_card_clock_overdue', clock.get('class'))
        self.assertFalse(clock.xpath('.//span[contains(@class, "o_pk_card_badge")]'))
        # Archive through an outside form / a sheet; trash shown in read mode.
        root = self._render('pk_card_icons', {'ci_archive': {'form': 'pk_t_form', 'label': 'Put away'},
                                              'ci_trash': {'form': 'pk_t_del', 'always': True, 'cls': 'pk_t_x'}})
        archive = root.xpath('.//button[@data-pk-card-archive]')[0]
        self.assertEqual((archive.get('type'), archive.get('form'), archive.get('aria-label')),
                         ('submit', 'pk_t_form', 'Put away'))
        trash = root.xpath('.//button[@data-pk-card-trash]')[0]
        self.assertIsNone(trash.get('hidden'))
        self.assertIsNone(trash.get('data-pk-edit-only'))
        self.assertIn('pk_t_x', trash.get('class'))

    # ------------------------------------------------------------- UC-C3
    def test_history(self):
        entries = [
            {'when': '1 Jan 2026 10:00', 'author': 'Test User', 'action': 'Edited', 'tone': 'green',
             'body': 'New text', 'state': '', 'scope': 'internal'},
            {'when': '2 Jan 2026 11:00', 'author': '', 'action': '', 'tone': 'ghost', 'body': '',
             'state': 'cleared'},
        ]
        root = self._render('pk_history_list', {'entries': entries, 'empty_message': 'None yet',
                                                'section': 'pk.t.history'},
                            body='<span class="pk_t_filters">filters</span>')
        frag = root.xpath('./div[contains(@class, "o_pk_history_fragment")]')[0]
        self.assertEqual(frag.get('data-pk-section'), 'pk.t.history')
        self.assertTrue(frag.xpath('./span[@class="pk_t_filters"]'))
        items = frag.xpath('.//li[contains(@class, "o_pk_history_entry")]')
        self.assertEqual([li.get('data-pk-scope') for li in items], ['internal', None])
        self.assertEqual([li.get('data-pk-history-state') for li in items], [None, 'cleared'])
        self.assertEqual(items[0].xpath('.//span[contains(@class, "o_pk_chip_green")]/text()'), ['Edited'])
        self.assertEqual(items[0].xpath('.//p[contains(@class, "o_pk_history_body")]/text()'), ['New text'])
        self.assertEqual(items[1].xpath('.//p[contains(@class, "o_pk_history_cleared")]/text()'), ['Cleared'])
        root = self._render('pk_history_list', {'entries': [], 'empty_message': 'None yet'})
        self.assertEqual(root.xpath('.//p[@class="o_pk_empty"]/text()'), ['None yet'])

    # ------------------------------------------------------------- UC-C4
    def test_banners(self):
        root = self._render('pk_banner', {'title': 'Note', 'tone': 'warn'}, body='Text')
        banner = root.xpath('./div')[0]
        self.assertEqual(banner.get('class'), 'o_pk_banner o_pk_banner_warn')
        self.assertIsNone(banner.get('data-pk-flash-error'))
        root = self._render('pk_flash_banners', {'pk_flash': {'success': 'Saved.', 'error': 'Refused.'}})
        banners = root.xpath('./div')
        self.assertEqual([b.get('class') for b in banners], ['o_pk_banner o_pk_banner_info', 'o_pk_banner o_pk_banner_warn'])
        self.assertEqual([b.get('data-pk-flash-error') for b in banners], [None, '1'])
        self.assertEqual([b.text_content().strip() for b in banners], ['Saved.', 'Refused.'])
        self.assertEqual(len(self._render('pk_flash_banners', {'pk_flash': {}})), 0)

    # ------------------------------------------------------------- UC-C5
    def test_switch(self):
        root = self._render('pk_switch', {'sw_name': 'pk_t_flag', 'sw_value': '1', 'sw_off': '0', 'sw_checked': False,
                                          'sw_disabled': True, 'sw_reason': 'Locked for now', 'sw_id': 'pk_t_sw'},
                            slots={'sw_label': 'A flag'})
        row = root.xpath('./label')[0]
        self.assertEqual(row.get('data-pk-switch-locked'), '1')
        reason = row.xpath('.//small[@data-pk-switch-reason="1"]')[0]
        self.assertIn('o_pk_switch_reason', reason.get('class'))
        self.assertEqual(reason.text, 'Locked for now')
        box = row.xpath('.//input[@type="checkbox"]')[0]
        self.assertEqual((box.get('id'), box.get('disabled'), box.get('aria-checked')), ('pk_t_sw', 'disabled', 'false'))
        twin = row.xpath('.//input[@type="hidden"][@data-pk-switch-off]')[0]
        self.assertEqual((twin.get('name'), twin.get('value'), twin.get('disabled')), ('pk_t_flag', '0', None))
        root = self._render('pk_switch', {'sw_checked': True}, slots={'sw_label': 'On'})
        self.assertIsNone(root.xpath('./label')[0].get('data-pk-switch-locked'))
        self.assertFalse(root.xpath('.//*[@data-pk-switch-reason]'))

    # ------------------------------------------------------------- UC-C6
    def test_confirm_sheet(self):
        root = self._render('pk_confirm_sheet', {
            'sheet_id': 'pk_t_confirm', 'title': 'Remove?', 'message': 'This removes it.', 'action': '/pk/t/remove',
            'hidden': {'item_id': 7}, 'confirm_label': 'Remove', 'danger': True,
        })
        dialog = root.xpath('./dialog[@id="pk_t_confirm"]')[0]
        form = dialog.xpath('.//form')[0]
        self.assertEqual((form.get('action'), form.get('method'), form.get('data-pk-guard')), ('/pk/t/remove', 'post', '1'))
        self.assertEqual(form.xpath('.//input[@name="item_id"]/@value'), ['7'])
        submit = form.xpath('.//button[@data-pk-confirm-submit="1"]')[0]
        self.assertIn('o_pk_btn_danger', submit.get('class'))
        self.assertEqual(submit.text, 'Remove')
        self.assertTrue(form.xpath('.//p[@id="pk_t_confirm_reason"]'))

    # ------------------------------------------------------------- UC-C7
    def test_link_row(self):
        links = [{'label': 'Group A', 'url': '/pk/t/group', 'icon': 'list', 'model': 'res.partner.category'},
                 {'name': 'Plain', 'url': False, 'model': 'res.partner'}]
        root = self._render('pk_link_row', {
            'href': '/pk/t/item', 'title': 'Item one',
            'title_parts': [{'text': 'Call '}, {'text': 'Item one', 'url': '/pk/t/item1', 'model': 'res.partner'}],
            'links': links, 'row_class': 'pk_t_row', 'dot': 'green',
        }, body='<span class="pk_t_trailing">x</span>')
        row = root.xpath('./div')[0]
        self.assertIn('o_pk_link_row', row.get('class'))
        self.assertIn('pk_t_row', row.get('class'))
        split = row.xpath('.//span[@data-pk-title-split="1"]')[0]
        self.assertEqual(split.xpath('./a[contains(@class, "o_pk_link_row_main")]/@aria-label'), ['Item one'])
        self.assertEqual(split.xpath('./a[@data-pk-title-link]/@data-pk-title-link'), ['res.partner'])
        holder = row.xpath('.//span[@data-pk-row-links="1"]')[0]
        self.assertEqual(holder.xpath('./a[@data-pk-row-link]/@data-pk-row-link'), ['res.partner.category'])
        self.assertEqual(holder.xpath('./span[@data-pk-row-link-plain]/@data-pk-row-link-plain'), ['res.partner'])
        self.assertTrue(row.xpath('.//span[@class="o_pk_row_trailing"]/span[@class="pk_t_trailing"]'))
        root = self._render('pk_link_row', {'href': '/pk/t/item', 'title': 'Item one', 'chevron': False})
        main = root.xpath('.//a[contains(@class, "o_pk_link_row_main")]')[0]
        self.assertEqual(main.text, 'Item one')
        self.assertFalse(root.xpath('.//*[@data-pk-title-split]'))
        root = self._render('pk_row_links', {'links': links})
        self.assertEqual(root.xpath('./a/@href'), ['/pk/t/group'])

    # ------------------------------------------------------------- UC-C8
    def test_entity_row(self):
        root = self._render('pk_entity_row', {'href': '/pk/t/item', 'title': 'Item one', 'subtitle': 'Sub',
                                              'lead_icon': 'list', 'row_attrs': {'data-pk-t': '1'}},
                            body='<span class="pk_t_chip">c</span>',
                            slots={'row_extra': '<span class="pk_t_extra">extra</span>'})
        row = root.xpath('./a')[0]
        self.assertEqual((row.get('href'), row.get('data-pk-t')), ('/pk/t/item', '1'))
        text = row.xpath('./span[@class="o_pk_row_text"]')[0]
        self.assertEqual(text.xpath('./span[@class="o_pk_row_title"]/text()'), ['Item one'])
        self.assertTrue(text.xpath('./span[@class="pk_t_extra"]'))
        self.assertTrue(row.xpath('./span[@class="o_pk_row_trailing"]/span[@class="pk_t_chip"]'))
        root = self._render('pk_entity_row', {'href': '/x', 'title': 'T', 'dot': 'red'})
        self.assertFalse(root.xpath('.//span[@class="pk_t_extra"]'))
        self.assertTrue(root.xpath('.//span[@class="o_pk_dot o_pk_tone_red"]'))

    def test_field_static_and_overdue(self):
        root = self._render('pk_field_static', {'label': 'Return', 'value': '1 Jan 2026', 'overdue': True})
        value = root.xpath('.//p[contains(@class, "o_pk_field_value")]')[0]
        self.assertIn('o_pk_overdue', value.get('class').split())
        flag = value.xpath('./span[@data-pk-overdue="1"]')[0]
        self.assertEqual((flag.get('class'), flag.text), ('o_pk_overdue_flag', 'Passed'))
        self.assertEqual(value.xpath('./span[@class="o_pk_overdue_sep"]/@aria-hidden'), ['true'])
        root = self._render('pk_field_static', {'label': 'Return', 'value': False})
        self.assertEqual(root.xpath('.//p[contains(@class, "o_pk_muted")]/text()'), ['—'])
        root = self._render('pk_field_static', {'value': 'v', 'no_label': True, 'static_hint': 'Hint'})
        self.assertFalse(root.xpath('.//span[@class="o_pk_field_label"]'))
        self.assertEqual(root.xpath('.//small[@class="o_pk_hint"]/text()'), ['Hint'])
        root = self._render('pk_overdue_flag')
        self.assertEqual(root.xpath('./span[@data-pk-overdue]/text()'), ['Passed'])
