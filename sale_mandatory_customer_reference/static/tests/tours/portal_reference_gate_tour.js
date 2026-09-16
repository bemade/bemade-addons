import { registry } from "@web/core/registry";

// Nicolas's repro (2026-09-15): reference empty -> Accept & Sign must not open
// the signature dialog; enter the reference -> it must work without a reload.
registry.category("web_tour.tours").add("sale_mandatory_customer_reference_portal_gate", {
    steps: () => [
        {
            content: "Warning shown and Accept & Sign disabled while the reference is missing",
            trigger: "#sale_order_sidebar_button .o_portal_reference_alert:not(.d-none)",
        },
        {
            content: "Still a real button (btn classes survive the gate)",
            trigger: "#sale_order_sidebar_button a.o_portal_reference_gate.btn.btn-primary.disabled",
        },
        {
            content: "Hint under the reference field is rendered on the order page",
            trigger: ".o_portal_sale_reference small",
        },
        {
            content: "No signature dialog is open",
            trigger: "body:not(:has(#modalaccept.show))",
        },
        {
            content: "Enter the PO reference",
            trigger: ".o_portal_sale_reference input[name='client_order_ref']",
            run(helpers) {
                const input = this.anchor;
                input.value = "PO-TOUR-1";
                input.dispatchEvent(new Event("change", { bubbles: true }));
            },
        },
        {
            content: "Reference saved: buttons enabled without a reload",
            trigger: "#sale_order_sidebar_button a.o_portal_reference_gate:not(.disabled)",
        },
        {
            trigger: ".o_portal_sale_reference .alert-success",
        },
        {
            content: "Accept & Sign now opens the signature dialog",
            trigger: "#sale_order_sidebar_button a.o_portal_reference_gate",
            run: "click",
        },
        {
            trigger: "#modalaccept.show .o_portal_sign_submit",
        },
    ],
});
