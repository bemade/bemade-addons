/*
 * Task 1749 — « Retours en retard » on the dashboard: a Match pill change
 * updates the card in place (tests/test_dashboard_overdue_refresh_1749.py,
 * phone 390 px and laptop 1440 px). Synthetic data; language-independent
 * triggers (data attributes, synthetic names). No reload: a marker on
 * window survives.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const LINE = 'section[data-sc-instance="todo"] details[data-sc-todo="returns"]';
const card = (name) => `${LINE} [data-sc-player-id]:has(.o_pk_row_title:contains("${name}"))`;

/** Practice « Oui », then Match « Oui » (Match needs Practice: Oui) on one
 * overdue card; each pick checked on the fresh card (pill + dot). */
function promote(name) {
    const sel = card(name);
    return [
        {
            content: `${name}: open the Practice pill`,
            trigger: `${sel} [data-pk-pill-key="practice"] > button`,
            run: "click",
        },
        {
            content: `${name}: Practice « Oui »`,
            trigger: `${sel} [data-pk-pill-key="practice"] [role="menuitemradio"][data-pk-pill-value="yes"]`,
            run: "click",
        },
        {
            content: `${name}: the card shows Practice « Oui » (still overdue: match « Non »)`,
            trigger: `${sel} [data-pk-pill-key="practice"] > button[data-pk-pill-value="yes"]`,
        },
        {
            content: `${name}: open the Match pill`,
            trigger: `${sel} [data-pk-pill-key="match"] > button[data-pk-pill-value="no"]`,
            run: "click",
        },
        {
            content: `${name}: Match « Oui »`,
            trigger: `${sel} [data-pk-pill-key="match"] [role="menuitemradio"][data-pk-pill-value="yes"]:not([aria-disabled="true"])`,
            run: "click",
        },
        {
            content: `${name}: the card follows at once — Match « Oui », green dot, no reload`,
            trigger: `${sel} [data-pk-pill-key="match"] > button[data-pk-pill-value="yes"]`,
            run() {
                const node = this.anchor.closest("[data-sc-player-id]");
                assert(node.querySelector(".o_pk_dot.o_pk_tone_green"), `${name}: green dot`);
                assert(window.__sc1749, "no reload");
            },
        },
    ];
}

tours.add("sc_1749_overdue_refresh", {
    steps: () => [
        {
            content: "Open « Overdue returns »",
            trigger: `${LINE} > summary`,
            run() {
                window.__sc1749 = true;
                this.anchor.click();
            },
        },
        // A visible card (the first of the line).
        ...promote("Synth, Red"),
        {
            content: "Unfold « See the N others »",
            trigger: `${LINE} details[data-sc-dw-more] > summary`,
            run: "click",
        },
        // A folded card.
        ...promote("Synth, Yellow"),
        // A folded card whose player is also in « Recent changes ».
        ...promote("Synth, Shared"),
        {
            content: "« Recent changes » shows the same, fresh",
            trigger: 'section[data-sc-instance="recent_changes"] [data-sc-player-id]:has(.o_pk_row_title:contains("Synth, Shared")) [data-pk-pill-key="match"] > button[data-pk-pill-value="yes"]',
        },
    ],
});
