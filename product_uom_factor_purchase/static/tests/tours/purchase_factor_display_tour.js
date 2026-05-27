import {registry} from "@web/core/registry";

registry.category("web_tour.tours").add("purchase_factor_display_tour", {
    steps: () => [
        {
            trigger: ".o_form_view .o_field_one2many[name='order_line']",
            content: "Wait for the order line list to load",
        },
        {
            // The optional column "Base UoM" should show the cross-category
            // equivalent quantity, e.g. "= 150.00 lb".
            trigger:
                ".o_field_one2many[name='order_line'] .o_list_renderer " +
                "td[name='factor_base_uom_display']:contains('= ')",
            content: "Base UoM column shows the cross-category quantity",
        },
    ],
});
