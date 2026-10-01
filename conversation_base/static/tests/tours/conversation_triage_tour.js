import { registry } from "@web/core/registry";

const row = (name) => `.o_data_row:has(.o_conversation_name:contains("${name}"))`;
const noRow = (name) =>
    `.o_list_renderer:not(:has(.o_conversation_name:contains("${name}"))):has(.o_data_row)`;
const focused = (name) =>
    `.o_data_row.o_conversation_row_focused:has(.o_conversation_name:contains("${name}"))`;

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
const key = (content, combo) => ({
    content,
    trigger: ".o_list_renderer",
    run: `press ${combo}`,
});

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
        // Keyboard accelerator on my inbox: Alpha, Delta, Echo, Foxtrot.
        {
            content: "Drop the done facet",
            trigger: ".o_control_panel .o_searchview_facet .o_facet_remove",
            run: "click",
        },
        noFacet,
        openFilters,
        toggleFilter("My Inbox"),
        { content: "Back on my inbox", trigger: noRow("Triage Charlie") },
        key("j focuses the first row", "j"),
        { content: "Alpha is focused", trigger: focused("Triage Alpha") },
        key("j moves down", "j"),
        { content: "Delta is focused", trigger: focused("Triage Delta") },
        key("k moves up", "k"),
        { content: "Alpha is focused again", trigger: focused("Triage Alpha") },
        key("j", "j"),
        { content: "Delta again", trigger: focused("Triage Delta") },
        key("Shift+j extends the selection", "shift+j"),
        {
            content: "Two rows are selected",
            trigger: ".o_selection_box:contains('2 selected')",
        },
        { content: "Echo has the focus", trigger: focused("Triage Echo") },
        key("Escape clears the selection", "Escape"),
        {
            content: "No selection left",
            trigger: ".o_control_panel:not(:has(.o_selection_box))",
        },
        key("k", "k"),
        { content: "Delta is focused", trigger: focused("Triage Delta") },
        key("e marks the focused row done", "e"),
        { content: "Delta is gone", trigger: noRow("Triage Delta") },
        { content: "Focus lands on the next row", trigger: focused("Triage Echo") },
        key("s opens the snooze dialog", "s"),
        {
            content: "Pick tomorrow morning",
            trigger: ".o_conversation_snooze_dialog [data-preset='tomorrow']",
            run: "click",
        },
        { content: "Echo is gone", trigger: noRow("Triage Echo") },
        { content: "Focus lands on Foxtrot", trigger: focused("Triage Foxtrot") },
        {
            content: "Focus the search input",
            trigger: ".o_searchview_input",
            run: "click",
        },
        {
            content: "k typed in the search input does not move the focus",
            trigger: ".o_searchview_input",
            run: "press k",
        },
        { content: "Foxtrot is still focused", trigger: focused("Triage Foxtrot") },
    ],
});
