/*
 * Task 1600 — a player's identity changes only through a visible
 * confirmation (tests/test_identity_guard_tours_1600.py). Language-
 * independent triggers; synthetic data.
 */
import { registry } from "@web/core/registry";

const tours = registry.category("web_tour.tours");

function assert(condition, message) {
    if (!condition) {
        throw new Error(message);
    }
}

// ------------------------------------- legacy edit form (app shell switch OFF)
tours.add("sc_1600_legacy_confirm", {
    steps: () => [
        {
            content: "Correct the first name",
            trigger: '#edit-player-form input[name="first_name"]',
            run: "edit Patty",
        },
        {
            content: "Untick the second team",
            trigger: '#edit-player-form input[name="team_ids"][data-sc-was-checked]:checked:not([data-sc-tour-keep])',
            run(helpers) {
                const boxes = [...document.querySelectorAll('#edit-player-form input[name="team_ids"][data-sc-was-checked]')];
                assert(boxes.length === 2, `ticked teams: ${boxes.length}`);
                boxes[0].dataset.scTourKeep = "1";
                return helpers.click(boxes[1]);
            },
        },
        {
            content: "Save: the confirm step shows instead of submitting",
            trigger: '#edit-player-form button[type="submit"]:last',
            run: "click",
        },
        {
            content: "The confirm step lists old → new and the team to leave",
            trigger: "#sc-save-confirm:not(.d-none)",
            run() {
                const identity = document.querySelector("#sc-confirm-identity-list").textContent;
                assert(identity.includes("Pat → Patty"), `identity list: ${identity}`);
                const teams = document.querySelector("#sc-confirm-teams-list").textContent;
                assert(teams.includes("PC Team C 1600"), `teams list: ${teams}`);
                assert(
                    document.querySelector('input[name="identity_confirmed"]').value === "0",
                    "confirmed before the click"
                );
            },
        },
        {
            content: "Back to the form: nothing sent",
            trigger: "#sc-confirm-cancel",
            run: "click",
        },
        {
            content: "Save again",
            trigger: "#sc-save-confirm.d-none:not(:visible)",
            run() {
                document.querySelector('#edit-player-form button[type="submit"]').click();
            },
        },
        {
            content: "Confirm and save",
            trigger: "#sc-save-confirm:not(.d-none) #sc-confirm-ok",
            run: "click",
            expectUnloadPage: true,
        },
        {
            content: "Landed on the player page",
            trigger: "body:not(:has(#edit-player-form))",
            run() {
                assert(window.location.pathname === "/my/player", window.location.href);
            },
        },
    ],
});

// ------------------------------------- app-shell pencil (switch ON)
tours.add("sc_1600_pencil_confirm", {
    steps: () => [
        {
            content: "Pencil of the identity card",
            trigger: '[data-pk-edit-card="identity"] button[data-pk-edit-toggle]',
            run: "click",
        },
        {
            content: "Correct the last name",
            trigger:
                '[data-pk-edit-card="identity"] [data-pk-edit-view="edit"]:not([hidden]) .o_pk_autosave[data-pk-autosave-field="last_name"] input',
            run: "edit Onesynth",
        },
        {
            content: "Leave the field",
            trigger: ".o_pk_appbar_title",
            run: "click",
        },
        {
            content: "The confirmation shows old → new; nothing saved yet",
            trigger: '.o_pk_autosave[data-pk-autosave-field="last_name"][data-pk-autosave-state="confirm"] .o_pk_confirm_banner',
            run() {
                const text = document.querySelector(".o_pk_confirm_banner .o_pk_confirm_change").textContent;
                assert(text.includes("One → Onesynth"), `banner: ${text}`);
            },
        },
        {
            content: "Cancel: back to the saved value",
            trigger: ".o_pk_confirm_banner .o_pk_confirm_cancel",
            run: "click",
        },
        {
            content: "The field shows the saved value again",
            trigger: '.o_pk_autosave[data-pk-autosave-field="last_name"][data-pk-autosave-state="idle"]:not(:has(.o_pk_confirm_banner)) input',
            run(helpers) {
                assert(helpers.anchor.value === "One", `value: ${helpers.anchor.value}`);
                return helpers.edit("Onesynth");
            },
        },
        {
            content: "Leave the field again",
            trigger: ".o_pk_appbar_title",
            run: "click",
        },
        {
            content: "Confirm",
            trigger: '.o_pk_autosave[data-pk-autosave-field="last_name"] .o_pk_confirm_banner .o_pk_confirm_ok',
            run: "click",
        },
        {
            content: "Saved",
            trigger: '.o_pk_autosave[data-pk-autosave-field="last_name"][data-pk-autosave-state="saved"]:not(:has(.o_pk_confirm_banner))',
        },
    ],
});
