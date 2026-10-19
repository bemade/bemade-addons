/*
 * Task 1607 — the list header (tests/test_list_header_tours_1607.py).
 *
 * sc_1607_players (laptop 1366 px and phone 360 px): no page action in the
 * app bar; the players list header fits on one line right above the list
 * (no sideways scroll, 44 px targets); the sort menu opens on the checked
 * option, Escape closes it, choosing « Alphabetical » reloads sorted; then
 * « + Ajouter » opens the player creation.
 * sc_1607_team_add: on the team roster, « + Ajouter » opens the add-player
 * panel right under the header (focus in its first field) and closes it.
 * Language-independent triggers (ids, data attributes, hrefs).
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const HEADER = '.o_sc_list_header[data-sc-section="players.header"]';
const TOGGLE = `${HEADER} button[data-sc-menu-toggle][aria-controls="sc_players_sort"]`;
const POPUP = "#sc_players_sort";

tours.add("sc_1607_players", {
    steps: () => [
        {
            content: "One header line right above the list; nothing in the app bar",
            trigger: HEADER,
            run() {
                const header = document.querySelector(HEADER);
                assert(!document.querySelector("header.o_sc_appbar .o_sc_appbar_action"),
                    "a page action is still in the app bar");
                const add = header.querySelector(".o_sc_list_add");
                const toggle = header.querySelector("button[data-sc-menu-toggle]");
                const a = add.getBoundingClientRect();
                const t = toggle.getBoundingClientRect();
                assert(a.height >= 44 && t.height >= 44, `targets ${a.height} / ${t.height}px tall`);
                assert(Math.abs(a.top - t.top) < 4, "« + Ajouter » and the sort are not on one line");
                assert(a.left < t.left, "the sort is not on the right");
                const h = header.getBoundingClientRect();
                assert(t.right <= h.right + 0.5, "the sort overflows the header");
                assert(document.documentElement.scrollWidth <= window.innerWidth + 0.5,
                    "the page scrolls sideways");
                const next = header.nextElementSibling;
                assert(next && next.matches('[data-sc-section="players.list"], .o_sc_empty'),
                    "the list does not follow the header");
            },
        },
        {
            content: "Open the sort menu",
            trigger: `${TOGGLE}[aria-expanded="false"]`,
            run: "click",
        },
        {
            content: "Open on the checked option, on screen",
            trigger: `${TOGGLE}[aria-expanded="true"]`,
            run() {
                const popup = document.querySelector(POPUP);
                assert(!popup.hidden, "the menu is hidden");
                const checked = popup.querySelector('[role="menuitemradio"][aria-checked="true"]');
                assert(checked && document.activeElement === checked, "focus is not on the checked option");
                const rect = popup.getBoundingClientRect();
                assert(rect.left >= 0 && rect.right <= window.innerWidth + 0.5,
                    `the menu overflows the screen: ${rect.left}-${rect.right} / ${window.innerWidth}`);
            },
        },
        {
            content: "Escape closes it and gives the focus back",
            trigger: `${POPUP}:not([hidden]) [role="menuitemradio"][aria-checked="true"]`,
            run: "press Escape",
        },
        {
            trigger: `${TOGGLE}[aria-expanded="false"]`,
            run() {
                assert(document.querySelector(POPUP).hidden, "the menu stays open");
                assert(document.activeElement === document.querySelector(TOGGLE), "focus not back on the toggle");
            },
        },
        {
            trigger: TOGGLE,
            run: "click",
        },
        {
            content: "Choose « Alphabetical »",
            trigger: `${POPUP}:not([hidden]) a[data-sc-sort="name"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Reloaded sorted alphabetically, the choice checked",
            trigger: `${TOGGLE}[aria-expanded="false"]`,
            run() {
                assert(new URL(window.location.href).searchParams.get("sort") === "name", "no sort=name");
                assert(document.querySelector(`${POPUP} a[data-sc-sort="name"][aria-checked="true"]`),
                    "« Alphabetical » is not checked");
            },
        },
        {
            content: "« + Ajouter » opens the player creation",
            trigger: `${HEADER} a.o_sc_list_add[data-sc-action="players.create"]`,
            run: "click",
            expectUnloadPage: true,
        },
        {
            trigger: 'body:has(.o_sc_app) form[action="/my/player/create/save"], body:has(.o_sc_app) form[data-sc-form]',
            run() {
                assert(window.location.pathname === "/my/player/create", window.location.pathname);
            },
        },
    ],
});

const ADD = '.o_sc_list_header[data-sc-section="team.roster.header"] button.o_sc_list_add[aria-controls="sc_add_player"]';

tours.add("sc_1607_team_add", {
    steps: () => [
        {
            content: "The add panel is closed and takes no room",
            trigger: `${ADD}[aria-expanded="false"]`,
            run() {
                const panel = document.getElementById("sc_add_player");
                assert(!panel.open && !panel.getClientRects().length, "the closed panel shows");
            },
        },
        {
            content: "« + Ajouter » opens it right under the header",
            trigger: ADD,
            run: "click",
        },
        {
            trigger: `${ADD}[aria-expanded="true"]`,
            run() {
                const panel = document.getElementById("sc_add_player");
                assert(panel.open, "the panel did not open");
                const header = document.querySelector(ADD).closest(".o_sc_list_header");
                assert(header.nextElementSibling === panel, "the panel is not under the header");
                assert(document.activeElement && panel.contains(document.activeElement),
                    "the focus is not in the panel");
                assert(document.activeElement.name === "add_first", `focus on ${document.activeElement.name}`);
            },
        },
        {
            content: "« + Ajouter » again closes it",
            trigger: ADD,
            run: "click",
        },
        {
            trigger: `${ADD}[aria-expanded="false"]`,
            run() {
                assert(!document.getElementById("sc_add_player").open, "the panel stays open");
            },
        },
    ],
});
