/*
 * Task 1656 — removing the only access team of a player
 * (tests/test_lose_access_confirm_1656.py, laptop).
 *
 * From the team page to the player's Infos → Teams pencil: the × of the
 * access team opens the popup; « Cancel » keeps the tag and saves nothing;
 * « Remove and leave » lands back on the team page with the toast, no 403.
 *
 * Phone tap-through stays UNVERIFIED until /dev-review.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

const TEAMS = 'section[data-sc-edit-card="teams"]';
const REMOVE = `${TEAMS} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="sc_team_ids"] .o_sc_tag:contains("PC Team A") button.o_sc_tag_remove`;

function removeButton() {
    const tag = [...document.querySelectorAll(
        `${TEAMS} [data-sc-edit-view="edit"]:not([hidden]) .o_sc_autosave[data-sc-field="sc_team_ids"] .o_sc_tag`
    )].find((li) => li.textContent.includes("PC Team A"));
    return tag ? tag.querySelector("button.o_sc_tag_remove") : null;
}

tours.add("sc_1656_lose_access", {
    steps: () => [
        {
            content: "From the team page, open the player",
            trigger: ".o_sc_app",
            run() {
                const link = document.querySelector('a[href*="/my/player?player_id="]');
                assert(link, "no player link on the team page");
                window.location.assign(link.getAttribute("href").replace(/&tab=[^&]*/, "") + "&tab=info");
            },
            expectUnloadPage: true,
        },
        {
            content: "Teams pencil",
            trigger: `${TEAMS} button[data-sc-edit-toggle]`,
            run: "click",
        },
        {
            content: "× on the access team: the popup",
            trigger: REMOVE,
            run() {
                window.__sc1656Saves = 0;
                document.addEventListener("sc:saved", () => (window.__sc1656Saves += 1));
                this.anchor.click();
            },
        },
        {
            content: "Cancel: the tag stays, nothing saved",
            trigger: "dialog[data-sc-confirm][open] [data-sc-confirm-cancel]",
            async run() {
                this.anchor.click();
                await new Promise((resolve) => setTimeout(resolve, 400));
                assert(removeButton(), "the tag went");
                assert(window.__sc1656Saves === 0, "something was saved");
            },
        },
        {
            content: "× again → « Remove and leave »",
            trigger: REMOVE,
            run: "click",
        },
        {
            trigger: "dialog[data-sc-confirm][open] [data-sc-confirm-ok]",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Back on the team page, the toast",
            trigger: '.o_sc_app .o_sc_toast:not([hidden]):contains("removed from")',
            run() {
                assert(window.location.pathname === "/my/team", window.location.pathname);
            },
        },
    ],
});
