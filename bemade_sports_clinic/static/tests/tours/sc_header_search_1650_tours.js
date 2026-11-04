/*
 * Task 1650 — the header search in a browser (tests/test_header_search_1650.py).
 *
 * sc_1650_search_tap (390 px): the magnifier opens the full-screen sheet,
 * the input has the focus; « eloi » lists Éloïse (openable) and Eloi
 * (another team: locked, not a link); a tap on Éloïse opens her page.
 * sc_1650_search_keys (1366 px): « / » opens the sheet; ArrowDown + Enter
 * open the first result.
 *
 * The iPhone keyboard / full-screen panel stay UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const SHEET = "dialog#sc_search_sheet";
const INPUT = `${SHEET}[open] input[data-sc-search-input]`;

tours.add("sc_1650_search_tap", {
    steps: () => [
        {
            content: "The magnifier opens the search",
            trigger: "header.o_sc_appbar a[data-sc-search-open]",
            run: "click",
        },
        {
            content: "Full screen, the input focused; type « eloi »",
            trigger: INPUT,
            run(helpers) {
                assert(document.activeElement === this.anchor, "the search input is not focused");
                const rect = document.querySelector(SHEET).getBoundingClientRect();
                assert(rect.height >= window.innerHeight - 2, `not full screen: ${rect.height}`);
                return helpers.edit("eloi");
            },
        },
        {
            content: "Éloïse openable, Eloi (other team) locked",
            trigger: `${SHEET} li.o_sc_search_locked`,
            run() {
                const locked = document.querySelector(`${SHEET} li.o_sc_search_locked`);
                assert(!locked.querySelector('a[href*="/my/player?"]'), "a locked row is a link");
                assert(locked.querySelector("a.o_sc_search_add"), "no « Add to team »");
            },
        },
        {
            content: "Tap Éloïse",
            trigger: `${SHEET} li:not(.o_sc_search_locked):not(.o_sc_search_archived) a.o_sc_search_link:contains("Synthétique")`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Her page",
            trigger: ".o_sc_app .o_sc_appbar_title:contains(Synthétique)",
        },
    ],
});

tours.add("sc_1650_search_keys", {
    steps: () => [
        {
            content: "« / » opens the search",
            trigger: ".o_sc_app .o_sc_appbar",
            run() {
                document.activeElement && document.activeElement.blur();
                document.body.dispatchEvent(new KeyboardEvent("keydown", { key: "/", bubbles: true, cancelable: true }));
            },
        },
        {
            content: "Type « synth eloi »",
            trigger: INPUT,
            run: "edit synth eloi",
        },
        {
            content: "ArrowDown highlights the first result, Enter opens it",
            trigger: `${SHEET} [data-sc-search-result]`,
            run() {
                const input = document.querySelector(INPUT);
                input.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true }));
                const first = document.querySelector(`${SHEET} [data-sc-search-result]`);
                assert(first.classList.contains("o_sc_search_active"), "ArrowDown highlighted nothing");
                input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true }));
            },
            expectUnloadPage: true,
        },
        {
            content: "A player page",
            trigger: ".o_sc_app nav[data-sc-tabs]",
        },
    ],
});
