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
