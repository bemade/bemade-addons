/*
 * Task 1540 (epic #1535, P3) — event form behaviours of the app shell
 * (progressive enhancement; inert outside .o_sc_app). Replaces, in the
 * shell only, the legacy create / edit pages' inline scripts:
 *
 * - task 1608: teams and assigned staff are form-mode tags fields
 *   (sc_autosave_field) writing the CSV hidden inputs the routes accept
 *   (team_ids, assigned_staff_ids) — the organization select narrows the
 *   teams through the field's ``groupSelect`` (task 1597);
 * - « Nouveau lieu »: the venue sheet's form posts through scFetch to the
 *   CSRF-checked /my/venue/create (JSON answer); the created venue is added
 *   to the venue select and selected, the sheet closes; on the event page
 *   (task 1612) the same request also sets it on the event — task 1611: the
 *   page then shows it in place (an « sc:saved » of the venue), no reload;
 * - task 1608: the coverage times follow the event times exactly as in the
 *   legacy portal: an empty start opens on « now » (create); a new start
 *   sets the coverage start to it, the end to start + 2 h and the coverage
 *   end to that end; a new end sets the coverage end to it when it is empty
 *   or earlier. A date / time counts once COMPLETE (owner review
 *   2026-10-14): left (blur), Enter, or picked — never while typing.
 */
import { _t } from "@web/core/l10n/translation";
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

function inShell(el) {
    return Boolean(el && el.closest && el.closest(".o_sc_app"));
}

// ------------------------------------------------- task 1608: coverage snapping
const EVENT_DEFAULT_MINUTES = 120;

function pad(n) {
    return String(n).padStart(2, "0");
}

function formatLocal(dt) {
    return `${dt.getFullYear()}-${pad(dt.getMonth() + 1)}-${pad(dt.getDate())}T${pad(dt.getHours())}:${pad(dt.getMinutes())}`;
}

/** « YYYY-MM-DDTHH:MM » as a LOCAL date, or null. */
function parseLocal(value) {
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(value || "");
    if (!match) {
        return null;
    }
    const [, y, mo, d, h, mi] = match.map(Number);
    return new Date(y, mo - 1, d, h, mi, 0, 0);
}

function timeInput(form, name) {
    return form.querySelector(`input[type="datetime-local"][name="${name}"]`);
}

/** The event start changed: coverage start = start, end = start + 2 h, coverage end = end. */
export function snapFromStart(form) {
    const start = parseLocal((timeInput(form, "date_start") || {}).value);
    if (!start) {
        return;
    }
    const end = new Date(start.getTime() + EVENT_DEFAULT_MINUTES * 60000);
    const set = (name, dt) => {
        const input = timeInput(form, name);
        if (input) {
            input.value = formatLocal(dt);
            input.dataset.scCommitted = input.value;
        }
    };
    set("therapist_start", start);
    set("date_end", end);
    set("therapist_end", end);
}

/** The event end changed: coverage end = end when empty or earlier. */
export function snapFromEnd(form) {
    const endInput = timeInput(form, "date_end");
    const end = parseLocal(endInput && endInput.value);
    const coverage = timeInput(form, "therapist_end");
    if (!end || !coverage) {
        return;
    }
    const current = parseLocal(coverage.value);
    if (!current || current.getTime() < end.getTime()) {
        coverage.value = endInput.value;
        coverage.dataset.scCommitted = coverage.value;
    }
}

const SNAPS = { date_start: snapFromStart, date_end: snapFromEnd };

function snapInput(input) {
    if (!(input instanceof HTMLInputElement) || !(input.name in SNAPS)) {
        return null;
    }
    const form = input.closest("form[data-sc-event-form]");
    return form && inShell(form) ? form : null;
}

/** A complete, new value of the event start / end: apply its rule once. */
function commitTime(input) {
    const form = snapInput(input);
    input.dataset.scTyping = "";
    if (!form || (input.validity && input.validity.badInput) || !input.value) {
        return;
    }
    if (input.value === input.dataset.scCommitted) {
        return;
    }
    input.dataset.scCommitted = input.value;
    SNAPS[input.name](form);
}

function initEventForms() {
    for (const form of document.querySelectorAll("form[data-sc-event-form]")) {
        if (!inShell(form)) {
            continue;
        }
        for (const name of ["date_start", "date_end", "therapist_start", "therapist_end"]) {
            const input = timeInput(form, name);
            if (input) {
                input.dataset.scCommitted = input.value;
            }
        }
        const start = timeInput(form, "date_start");
        if (start && !start.value && form.dataset.scEventFormMode !== "edit") {
            // Legacy portal: a new event opens on « now », its times following.
            start.value = formatLocal(new Date());
            start.dataset.scCommitted = start.value;
            snapFromStart(form);
        }
    }
}

document.addEventListener("keydown", (ev) => {
    const input = ev.target;
    if (!snapInput(input)) {
        return;
    }
    if (ev.key === "Enter") {
        ev.preventDefault();
        commitTime(input);
    } else if (!["Tab", "Shift"].includes(ev.key)) {
        input.dataset.scTyping = "1";
    }
});

document.addEventListener("pointerdown", (ev) => {
    if (snapInput(ev.target)) {
        // Opening the picker: the next change is a pick.
        ev.target.dataset.scTyping = "";
    }
});

document.addEventListener("change", (ev) => {
    const input = ev.target;
    if (snapInput(input) && !input.dataset.scTyping) {
        commitTime(input);
    }
});

document.addEventListener("focusout", (ev) => {
    if (snapInput(ev.target)) {
        commitTime(ev.target);
    }
});

async function createVenue(form) {
    const error = form.querySelector("[data-sc-venue-error]");
    const data = Object.fromEntries(new FormData(form).entries());
    if (form.dataset.scVenueEvent) {
        // The event page's pencil card (owner review 2026-10-11): the venue
        // is created AND set on the event by the same request (task 1612 —
        // a refused assignment leaves no orphan venue), over the event's
        // write date and venue this page last saw.
        Object.assign(data, {
            event_id: form.dataset.scVenueEvent,
            write_date: form.dataset.scVenueEventWriteDate || "",
            old_value: form.dataset.scVenueEventVenue || "",
        });
    }
    if (error) {
        error.hidden = true;
    }
    try {
        const result = await scFetch(form.action, { method: "POST", data, toast: false });
        if (!result || !result.success) {
            throw new Error((result && result.error) || "");
        }
        if (form.dataset.scVenueEvent) {
            // Task 1611: no reload — the save is announced like an autosave
            // of the venue: the card's venue field takes the new choices and
            // value (« also »), the read view and the title refresh as read
            // fragments, the sheet's own write date follows (below).
            const recordId = Number(form.dataset.scVenueEvent);
            const shown = { value: result.id, display: result.name, options: result.venue_options };
            document.dispatchEvent(
                new CustomEvent("sc:saved", {
                    detail: {
                        model: "sports.event",
                        recordId,
                        field: "venue_id",
                        result: {
                            ok: true,
                            write_date: result.event_write_date,
                            value: result.id,
                            display: result.name,
                            also: { venue_id: shown },
                            refresh: result.refresh || [`sports.event:${recordId}:*`],
                            saved_at: result.saved_at,
                        },
                    },
                })
            );
            form.reset();
            const sheet = form.closest("dialog");
            if (sheet) {
                sheet.close();
            }
            return;
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
    if (form.dataset.scVenueForm) {
        ev.preventDefault();
        createVenue(form);
    }
});

// Task 1612: keep the event page's venue sheet in step with the card's
// autosaves (a sibling field moves the write date; a venue pick changes the
// venue the sheet will be compared against).
document.addEventListener("sc:saved", (ev) => {
    const detail = ev.detail || {};
    if (detail.model !== "sports.event" || !detail.result) {
        return;
    }
    for (const form of document.querySelectorAll("form[data-sc-venue-event]")) {
        if (String(form.dataset.scVenueEvent) !== String(detail.recordId)) {
            continue;
        }
        if (detail.result.write_date) {
            form.dataset.scVenueEventWriteDate = detail.result.write_date;
        }
        if (detail.field === "venue_id" && detail.result.value !== undefined) {
            form.dataset.scVenueEventVenue = String(detail.result.value || "");
        }
    }
});

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initEventForms);
} else {
    initEventForms();
}
