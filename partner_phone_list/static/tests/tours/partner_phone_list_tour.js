/** @odoo-module **/
// Copyright 2026 Bemade Inc. License LGPL-3.0 or later.
// Contact form: add two numbers, save, drag the second to the top, save.
import { registry } from "@web/core/registry";

const LIST = ".o_form_view div[name=phone_ids]";

registry.category("web_tour.tours").add("partner_phone_list_tour", {
    url: "/odoo/action-base.action_partner_form/new",
    steps: () => [
        {
            content: "Name the contact",
            trigger: ".o_field_widget[name='name'] textarea, .o_field_widget[name='name'] input",
            run: "edit Sample Tour Contact",
        },
        {
            content: "Add a first number",
            trigger: `${LIST} .o_field_x2many_list_row_add a`,
            run: "click",
        },
        {
            content: "Type the office number",
            trigger: `${LIST} tr.o_selected_row div[name=number] input`,
            run: "edit 514-555-0111",
        },
        {
            content: "Add a second number",
            trigger: `${LIST} .o_field_x2many_list_row_add a`,
            run: "click",
        },
        {
            content: "Open the type menu",
            trigger: `${LIST} tr.o_selected_row div[name=type] .o_select_menu_toggler`,
            run: "click",
        },
        {
            content: "Make it a mobile",
            trigger: ".o_select_menu_menu .o_select_menu_item:contains(Mobile)",
            run: "click",
        },
        {
            content: "Type the mobile number",
            trigger: `${LIST} tr.o_selected_row div[name=number] input`,
            run: "edit 514-555-0222",
        },
        {
            content: "Save",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved with two numbers",
            trigger: `.o_form_saved div[name=phone_ids] tbody tr.o_data_row:nth-child(2)`,
        },
        {
            content: "Drag the mobile to the top",
            trigger: `${LIST} tbody tr.o_data_row:nth-child(2) .o_row_handle`,
            run: `drag_and_drop(${LIST} tbody tr.o_data_row:nth-child(1))`,
        },
        {
            content: "Mobile is now first",
            trigger: `${LIST} tbody tr.o_data_row:nth-child(1):contains(0222)`,
        },
        {
            content: "Save again",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved",
            trigger: `.o_form_saved div[name=phone_ids] tbody tr.o_data_row:nth-child(1):contains(0222)`,
        },
    ],
});
