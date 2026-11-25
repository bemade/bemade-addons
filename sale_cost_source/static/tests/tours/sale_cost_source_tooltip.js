import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("sale_cost_source_tooltip", {
    steps: () => [
        {
            content: "The line shows its cost basis badge",
            trigger: ".o_field_x2many_list td[name='cost_source_confidence'] .badge",
        },
        {
            content: "The header shows the summary badge",
            trigger: "div[name='cost_source_summary'] .badge",
        },
        {
            content: "Hover the unit price",
            trigger: ".o_field_x2many_list td[name='price_unit'] .o_cost_source_price",
            run: "hover",
        },
        {
            content: "The tooltip lists the evidence",
            trigger: ".o-tooltip .o_cost_source_tooltip:contains('Unknown. No vendor price')",
        },
    ],
});
