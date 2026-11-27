import { registry } from "@web/core/registry";

// The test fixture has 5 criteria on a 5-level scale.
registry.category("web_tour.tours").add("hr_appraisal_campaign_self_evaluation_tour", {
    steps: () => [
        {
            content: "The word pictures are shown, one per level",
            trigger: ".o_campaign_wp .o_campaign_wp_criterion:eq(0) .o_campaign_wp_level_5",
        },
        {
            content: "Give an example on the first criterion",
            trigger: ".o_campaign_wp_criterion:eq(0) textarea.o_campaign_wp_examples",
            run: "edit Helped the night shift",
        },
        ...Array.from({ length: 5 }, (_, i) => ({
            content: `Grade criterion ${i + 1}: click the level 3 word picture`,
            trigger: `.o_campaign_wp .o_campaign_wp_criterion:eq(${i}) .o_campaign_wp_level[data-level='3']`,
            run: "click",
        })),
        {
            content: "The choice is highlighted",
            trigger: ".o_campaign_wp_criterion:eq(4) .o_campaign_wp_level_3.o_campaign_wp_selected",
        },
        {
            content: "Submit to the manager",
            trigger: "button[name='action_campaign_submit_self']",
            run: "click",
        },
        {
            content: "Confirm",
            trigger: ".modal-footer .btn-primary",
            run: "click",
        },
        {
            content: "The evaluation moved to the manager",
            trigger: ".o_statusbar_status .o_arrow_button_current:contains('Manager evaluation')",
        },
    ],
});
