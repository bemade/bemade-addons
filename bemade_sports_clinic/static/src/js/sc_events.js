/*
 * Task 1540 (epic #1535, P3) — event form behaviours of the app shell
 * (progressive enhancement; inert outside .o_sc_app). Replaces, in the
 * shell only, the legacy create / edit pages' inline scripts:
 *
 * - on submit, the team / staff checkbox lists are joined into the CSV
 *   fields the routes accept (team_ids, assigned_staff_ids): a form posts
 *   only one value per repeated name to Odoo;
 * - « Nouveau lieu »: the venue sheet's form posts through scFetch to the
 *   CSRF-checked /my/venue/create (JSON answer); the created venue is added
 *   to the venue select and selected, the sheet closes.
 */
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

function inShell(el) {
    return Boolean(el && el.closest && el.closest(".o_sc_app"));
}

function syncCsv(form) {
    for (const hidden of form.querySelectorAll("input[data-sc-csv-of]")) {
        const name = hidden.dataset.scCsvOf;
        hidden.value = [...form.querySelectorAll(`input[name="${name}"]:checked`)]
            .map((box) => box.value)
            .join(",");
    }
}

async function createVenue(form) {
    const error = form.querySelector("[data-sc-venue-error]");
    const data = Object.fromEntries(new FormData(form).entries());
    if (error) {
        error.hidden = true;
    }
    try {
        const result = await scFetch(form.action, { method: "POST", data, toast: false });
        if (!result || !result.success) {
            throw new Error((result && result.error) || "");
        }
        const select = document.querySelector("select[data-sc-venue-select]");
        if (select) {
            const option = document.createElement("option");
            option.value = String(result.id);
            option.textContent = result.name;
            select.appendChild(option);
            select.value = String(result.id);
        }
        form.reset();
        const dialog = form.closest("dialog");
        if (dialog) {
            dialog.close();
        }
    } catch (err) {
        if (error) {
            error.textContent = (err && err.message) || _t("The venue could not be created.");
            error.hidden = false;
        }
    }
}

document.addEventListener("submit", (ev) => {
    const form = ev.target;
    if (!(form instanceof HTMLFormElement) || !inShell(form)) {
        return;
    }
    if (form.dataset.scEventForm) {
        syncCsv(form);
    } else if (form.dataset.scVenueForm) {
        ev.preventDefault();
        createVenue(form);
    }
});
