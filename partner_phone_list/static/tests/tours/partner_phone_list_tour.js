/** @odoo-module **/
// Copyright 2026 Bemade Inc. License LGPL-3.0 or later.
// Contact form: open the phonebook dialog from the Phone row, add two numbers,
// check the displayed Phone, save; reopen, drag the second to the top, save
// from the dialog. Same in the child-contact popup (dialog in a dialog).
import { registry } from "@web/core/registry";

const DIALOG = ".o_partner_phone_list_dialog";
const LIST = `${DIALOG} div[name=phone_ids]`;
const MAIN_PHONE = ".o_form_view .o_form_sheet_bg .o_partner_phone_list_phone";

// Open a selection menu and pick an option. The new row's onchange can
// re-render the cell and close a menu opened too early, so re-open it until
// the option shows up.
async function pickInMenu(toggler, label) {
    for (let i = 0; i < 50; i++) {
        const item = [...document.querySelectorAll(".o_select_menu_menu .o_select_menu_item")].find(
            (el) => el.textContent.trim() === label
        );
        if (item) {
            item.click();
            return;
        }
        if (i % 10 === 0) {
            document.querySelector(toggler)?.click();
        }
        await new Promise((resolve) => setTimeout(resolve, 100));
    }
    throw new Error(`Option ${label} not found`);
}

// ``row``: the new line's position. On a slow runner "the selected row" can
// still be the previous line while the new one is being added.
function addNumberSteps(number, row, type) {
    const ROW = `${LIST} tbody tr.o_data_row:nth-child(${row}).o_selected_row`;
    const steps = [
        {
            content: `Add a number (${number})`,
            trigger: `${LIST} .o_field_x2many_list_row_add a`,
            run: "click",
        },
    ];
    if (type) {
        steps.push({
            content: `Make it a ${type} number`,
            trigger: `${ROW} div[name=type] .o_select_menu_toggler`,
            run: () => pickInMenu(`${ROW} div[name=type] .o_select_menu_toggler`, type),
        });
    }
    steps.push({
        content: `Type ${number}`,
        trigger: `${ROW} div[name=number] input`,
        run: `edit ${number}`,
    });
    return steps;
}

registry.category("web_tour.tours").add("partner_phone_list_tour", {
    url: "/odoo/action-base.action_partner_form/new",
    steps: () => [
        {
            content: "Name the contact",
            trigger: ".o_field_widget[name='name'] textarea, .o_field_widget[name='name'] input",
            run: "edit Sample Tour Contact",
        },
        {
            content: "Open the phonebook from the Phone row",
            trigger: `${MAIN_PHONE} .o_partner_phone_list_open`,
            run: "click",
        },
        ...addNumberSteps("514-555-0111", 1),
        ...addNumberSteps("514-555-0222", 2, "Mobile"),
        {
            content: "Done (new contact: kept in the form)",
            trigger: `${DIALOG} .o_partner_phone_list_save:contains(Done)`,
            run: "click",
        },
        {
            content: "The form shows the top number, formatted",
            trigger: `body:not(:has(${DIALOG})) ${MAIN_PHONE} .o_partner_phone_list_value:contains(+1 514-555-0111)`,
        },
        {
            content: "The Mobile row shows the mobile",
            trigger: ".o_form_view .o_partner_phone_list_mobile:contains(+1 514-555-0222)",
        },
        {
            content: "Save the contact",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved",
            trigger: ".o_form_saved",
        },
        {
            content: "Reopen the phonebook",
            trigger: `${MAIN_PHONE} .o_partner_phone_list_open`,
            run: "click",
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
            content: "Save from the dialog (saved contact: saved at once)",
            trigger: `${DIALOG} .o_partner_phone_list_save:contains(Save)`,
            run: "click",
        },
        {
            content: "Phone is now the mobile, the contact is saved",
            trigger: `body:not(:has(${DIALOG})):has(.o_form_saved) ${MAIN_PHONE} .o_partner_phone_list_value:contains(0222)`,
        },
        {
            content: "No separate Mobile row (the mobile is the top number)",
            trigger: ".o_form_view:not(:has(.o_form_sheet_bg .o_partner_phone_list_mobile))",
        },
    ],
});

registry.category("web_tour.tours").add("partner_phone_list_child_tour", {
    url: "/odoo/action-base.action_partner_form/new",
    steps: () => [
        {
            content: "Make it a company",
            trigger: ".o_field_widget[name=company_type] input[data-value=company]",
            run: "click",
        },
        {
            content: "Name the company",
            // wait for the company-mode name field: typing into the person one
            // just before the switch re-renders it loses the name
            trigger: ".o_field_widget[name='name'] :is(textarea, input)[placeholder*='Lumber']",
            run: "edit Sample Tour Company",
        },
        {
            content: "Add a child contact",
            trigger: "div[name=child_ids] .o-kanban-button-new",
            run: "click",
        },
        {
            content: "Name the child contact",
            trigger: ".modal .o_form_view .o_field_widget[name=name] input",
            run: "edit Sample Tour Child",
        },
        {
            content: "Open the phonebook from the popup",
            trigger: ".modal .o_form_view .o_partner_phone_list_phone .o_partner_phone_list_open",
            run: "click",
        },
        ...addNumberSteps("438-555-0133", 1, "Mobile"),
        {
            content: "Done (child contact: kept in its popup)",
            trigger: `${DIALOG} .o_partner_phone_list_save:contains(Done)`,
            run: "click",
        },
        {
            content: "The popup shows the number",
            trigger: `body:not(:has(${DIALOG})) .modal .o_partner_phone_list_phone .o_partner_phone_list_value:contains(+1 438-555-0133)`,
        },
        {
            content: "Save the child contact",
            trigger: ".modal .o_form_button_save",
            run: "click",
        },
        {
            content: "Popup closed",
            trigger: "body:not(:has(.modal))",
        },
        {
            content: "Save the company",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Saved",
            trigger: ".o_form_saved",
        },
    ],
});
