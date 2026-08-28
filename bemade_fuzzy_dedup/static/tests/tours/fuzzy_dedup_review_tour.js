import {registry} from "@web/core/registry";

/**
 * Walks the whole reviewer flow in a real browser: open a target, scan,
 * open the proposed group, merge it.
 *
 * The first step is the regression guard that matters most. The target form
 * carries a `widget="domain"` whose `model` option is resolved against the
 * record's loaded fields; when the named field is absent the widget passes the
 * string through as a model name and the form dies with an RPC 404. Python
 * cannot see that: Form() does not evaluate widget options, so the form tested
 * green while being broken for every user.
 */
registry.category("web_tour.tours").add("fuzzy_dedup_review_tour", {
  steps: () => [
    {
      trigger: ".o_form_view .o_field_widget[name='domain']",
      content:
        "The target form renders, domain widget included — it 404s here if " +
        "the field named by its `model` option is missing from the view",
    },
    {
      trigger: "button[name='action_scan']",
      content: "Scan for duplicates",
      run: "click",
    },
    {
      // Rows are grouped by match group and Odoo collapses groups by default,
      // so the group header has to be opened before its records are reachable.
      trigger: ".o_list_view .o_group_header",
      content: "The scan proposed a group — open it",
      run: "click",
    },
    {
      trigger: ".o_list_view .o_data_row td[name='compared_value']",
      content: "The records show the value they matched on",
    },
    {
      trigger: ".o_list_view .o_data_row button[name='action_merge_into']",
      content: "Keep this record and merge the rest of the group into it",
      run: "click",
    },
    {
      trigger: ".modal-footer button.btn-primary",
      content: "Confirm the merge — it is irreversible, so it asks first",
      run: "click",
    },
    {
      // The row buttons are invisible once the group leaves 'pending', so
      // their disappearance proves the round-trip landed. The resulting STATE
      // is asserted in Python, where it belongs.
      trigger: ".o_list_view:not(:has(button[name='action_merge_into']))",
      content: "The merge completed and the group left the pending state",
    },
  ],
});
