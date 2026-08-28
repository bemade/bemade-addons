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
      // A cell, not the row: clicking the <tr> itself does not open the
      // record in Odoo 19, so the tour would sit on the list and time out on
      // the next step.
      trigger: ".o_list_view .o_data_row td[name='model_name']",
      content: "The scan proposed at least one group — open it",
      run: "click",
    },
    {
      trigger: ".o_form_view .o_field_widget[name='record_ids'] .o_data_row",
      content: "The group lists the records it proposes merging",
    },
    {
      trigger: "button[name='action_merge']",
      content: "Merge the group",
      run: "click",
    },
    {
      trigger: ".modal-footer button.btn-primary",
      content: "Confirm the merge — it is irreversible, so it asks first",
      run: "click",
    },
    {
      trigger:
        ".o_form_view .o_statusbar_status button.o_arrow_button_current" +
        ":contains('Merged')",
      content: "The group ends up merged",
    },
  ],
});
