import { registry } from "@web/core/registry";

const row = (name) => `.o_data_row:has(.o_conversation_name:contains("${name}"))`;
const noRow = (name) =>
    `.o_list_renderer:not(:has(.o_conversation_name:contains("${name}"))):has(.o_data_row)`;
const openFilters = {
    content: "Open the filter menu",
    trigger: ".o_control_panel .o_searchview_dropdown_toggler",
    run: "click",
};
const toggleFilter = (label) => ({
    content: `Toggle the ${label} filter`,
    trigger: `.o_filter_menu .o_menu_item:contains("${label}")`,
    run: "click",
});
const clearFacets = {
    content: "Remove the search facet",
    trigger: ".o_control_panel .o_searchview_facet .o_facet_remove",
    run: "click",
};
const noFacet = {
    content: "No facet left",
    trigger: ".o_control_panel .o_searchview:not(:has(.o_searchview_facet))",
};
registry.category("web_tour.tours").add("conversation_triage_tour", {
    url: "/odoo/action-conversation_base.mail_conversation_action",
    steps: () => [
        {
            content: "The triage list shows the open conversations",
            trigger: row("Triage Alpha"),
        },
        {
            content: "Mark Alpha handled",
            trigger: `${row("Triage Alpha")} .o_conversation_action_handle`,
            run: "click",
        },
        { content: "Alpha left my list", trigger: noRow("Triage Alpha") },
        // Reach it again through the "Handled by me" view and put it back.
        clearFacets,
        noFacet,
        openFilters,
        toggleFilter("Handled by me"),
        { content: "Alpha is in the handled view", trigger: row("Triage Alpha") },
        {
            content: "Put Alpha back on my list",
            trigger: `${row("Triage Alpha")} .o_conversation_action_handle:contains("Back to my list")`,
            run: "click",
        },
        {
            content: "Alpha left the handled view",
            trigger: '.o_content:not(:has(.o_conversation_name:contains("Triage Alpha")))',
        },
        {
            content: "Drop the handled facet",
            trigger: ".o_control_panel .o_searchview_facet .o_facet_remove",
            run: "click",
        },
        noFacet,
        openFilters,
        toggleFilter("My Inbox"),
        { content: "Alpha is back in my inbox", trigger: row("Triage Alpha") },
        // Done on one row.
        {
            content: "Mark Bravo done",
            trigger: `${row("Triage Bravo")} .o_conversation_action_done`,
            run: "click",
        },
        { content: "Bravo is gone", trigger: noRow("Triage Bravo") },
        // Partial bulk: Alpha and Charlie, out of the rows still visible.
        {
            content: "Select Alpha",
            trigger: `${row("Triage Alpha")} .o_list_record_selector input`,
            run: "click",
        },
        {
            content: "Select Charlie",
            trigger: `${row("Triage Charlie")} .o_list_record_selector input`,
            run: "click",
        },
        {
            content: "Mark the selection done",
            trigger: `.o_control_panel button[name="action_triage_done"]`,
            run: "click",
        },
        { content: "Alpha is gone", trigger: noRow("Triage Alpha") },
        { content: "Charlie is gone", trigger: noRow("Triage Charlie") },
        { content: "Delta is untouched", trigger: row("Triage Delta") },
        // Reopen Alpha from the Done view, then follow Charlie's chip.
        clearFacets,
        noFacet,
        openFilters,
        toggleFilter("Done"),
        { content: "Alpha is in the done view", trigger: row("Triage Alpha") },
        {
            content: "Reopen Alpha",
            trigger: `${row("Triage Alpha")} .o_conversation_action_done:contains("Reopen")`,
            run: "click",
        },
        { content: "Alpha left the done view", trigger: noRow("Triage Alpha") },
        {
            content: "Click Charlie's linked-record chip",
            trigger: `${row("Triage Charlie")} .o_conversation_chip:contains("Tour Partner")`,
            run: "click",
        },
        {
            content: "The partner form opened",
            trigger: `.o_form_view .o_field_widget[name="name"] input:value("Tour Partner")`,
        },
        {
            content: "Back to the list",
            trigger: ".o_control_panel .breadcrumb-item:contains('Conversations')",
            run: "click",
        },
        { content: "The list is back", trigger: row("Triage Charlie") },
    ],
});
