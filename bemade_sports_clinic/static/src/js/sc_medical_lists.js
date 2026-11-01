/*
 * Task 1677 — the medical popups' structured lists (sc_medical_sheets;
 * controllers/app_critical_items.py). Inert outside .o_sc_app.
 *
 * - form[data-sc-med-add] (the list header's « + Ajouter » panel) adds an
 *   item; the panel is reset and closed after a successful add (#1672);
 * - an item card's edit view (its pencil, sc_app_ui.js; the pencil turns
 *   into the ✓ that closes it, #1676): each [data-sc-med-item-field] input
 *   is saved on change; [data-sc-med-item-delete] (the trash can) removes
 *   the item;
 * - [data-sc-med-set] inputs (the EpiPen card, « none known ») save one
 *   field of the player; the EpiPen note shows only while EpiPen is ticked.
 *
 * Each answer is announced as an « sc:saved » of the player (its
 * ``refresh`` patterns): the pills, the popup's head pill, the list (a
 * « list » fragment — the open cards keep their state), the cards follow in
 * place, without a reload.
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";
import { resetAddPanel } from "@bemade_sports_clinic/js/sc_list_header";

function sheetOf(el) {
    return el && el.closest && el.closest(".o_sc_app .o_sc_med_sheet");
}

function announce(sheet, result) {
    document.dispatchEvent(
        new CustomEvent("sc:saved", {
            detail: {
                model: "sports.patient",
                recordId: Number(sheet.dataset.scPatient),
                field: `medical.${result.family || sheet.dataset.scMedFamily}`,
                result,
                source: "medical-lists",
            },
        })
    );
}

function showError(holder, message) {
    const box = holder && holder.querySelector("[data-sc-med-error]");
    if (box) {
        box.textContent = message || "";
        box.hidden = !message;
    }
}

function messageOf(error) {
    return (error && error.payload && error.payload.message) || "";
}

function inputValue(input) {
    if (input.type === "checkbox") {
        return input.checked ? "1" : "0";
    }
    return input.value;
}

function radioGroup(input) {
    return [...document.querySelectorAll(`input[type="radio"][name="${CSS.escape(input.name)}"]`)];
}

function revert(input) {
    if (input.type === "radio") {
        for (const radio of radioGroup(input)) {
            radio.checked = radio.defaultChecked;
        }
    } else if (input.type === "checkbox") {
        input.checked = input.defaultChecked;
        // Task 1726: a switch's aria-checked follows (sc_switch.js).
        input.setAttribute("aria-checked", input.checked ? "true" : "false");
    } else {
        input.value = input.defaultValue;
    }
}

function commit(input) {
    if (input.type === "radio") {
        for (const radio of radioGroup(input)) {
            radio.defaultChecked = radio.checked;
        }
    } else if (input.type === "checkbox") {
        input.defaultChecked = input.checked;
    } else {
        input.defaultValue = input.value;
    }
}

function syncEpipenNote(sheet, ticked) {
    for (const field of sheet.querySelectorAll("[data-sc-med-epipen-note-field]")) {
        field.hidden = !ticked;
    }
}

// ------------------------------------------------------------------ add
document.addEventListener(
    "submit",
    async (ev) => {
        const form = ev.target;
        if (!(form instanceof HTMLFormElement) || !form.matches("form[data-sc-med-add]")) {
            return;
        }
        const sheet = sheetOf(form);
        if (!sheet) {
            return;
        }
        ev.preventDefault();
        const button = form.querySelector('button[type="submit"]');
        const data = {
            patient_id: form.dataset.scPatient,
            family: form.dataset.scFamily,
            name: form.elements.name.value,
            life_threatening: form.elements.life_threatening && form.elements.life_threatening.checked ? "1" : "",
            first_aid_note: form.elements.first_aid_note ? form.elements.first_aid_note.value : "",
        };
        button.disabled = true;
        showError(form, "");
        try {
            const result = await scFetch("/my/app/medical/item/add", { method: "POST", data, toast: false });
            if (document.activeElement && form.contains(document.activeElement)) {
                document.activeElement.blur();
            }
            resetAddPanel(form);
            announce(sheet, result);
        } catch (error) {
            showError(form, messageOf(error));
        } finally {
            button.disabled = false;
        }
    },
    true
);

// --------------------------------------------------------- item fields
async function saveItemField(input) {
    const card = input.closest("[data-sc-med-item]");
    const sheet = sheetOf(input);
    if (!card || !sheet) {
        return;
    }
    const field = input.dataset.scMedItemField;
    showError(card, "");
    try {
        const result = await scFetch(`/my/app/medical/item/${card.dataset.scMedItem}/save`, {
            method: "POST",
            data: { [field]: inputValue(input) },
            toast: false,
        });
        commit(input);
        announce(sheet, result);
    } catch (error) {
        revert(input);
        showError(card, messageOf(error));
    }
}

// ---------------------------------------------------------- player fields
async function savePlayerField(input) {
    const sheet = sheetOf(input);
    if (!sheet) {
        return;
    }
    const field = input.dataset.scMedSet;
    const holder = input.closest(".o_sc_med_card_edit, .o_sc_med_none_box") || sheet;
    if (input.type === "radio" && !input.checked) {
        return;
    }
    const value = input.type === "checkbox" ? (input.checked ? "1" : "") : input.value;
    // Task 1717: the Yes / No answer (radios) drives the note like the old box.
    const epipenOn = field === "allergy_epipen_state" ? value === "yes" : input.checked;
    if (field === "allergy_epipen" || field === "allergy_epipen_state") {
        syncEpipenNote(sheet, epipenOn);
    }
    if (input.type === "checkbox" && input.closest("[data-sc-fragment]")) {
        // A focused element pins its read fragment (#1641).
        input.blur();
    }
    showError(holder, "");
    try {
        const result = await scFetch(`/my/app/medical/${sheet.dataset.scPatient}/set`, {
            method: "POST",
            data: { field, value },
            toast: false,
        });
        commit(input);
        if ((field === "allergy_epipen" || field === "allergy_epipen_state") && !epipenOn) {
            // The note goes with the EpiPen (the server clears it).
            for (const note of sheet.querySelectorAll('[data-sc-med-set="allergy_epipen_note"]')) {
                note.value = "";
                note.defaultValue = "";
            }
        }
        announce(sheet, result);
    } catch (error) {
        revert(input);
        if (field === "allergy_epipen") {
            syncEpipenNote(sheet, input.checked);
        }
        if (field === "allergy_epipen_state") {
            const checked = sheet.querySelector('[data-sc-med-set="allergy_epipen_state"]:checked');
            syncEpipenNote(sheet, Boolean(checked && checked.value === "yes"));
        }
        showError(holder, messageOf(error));
    }
}

document.addEventListener("change", (ev) => {
    const input = ev.target;
    if (!input || !input.closest || !sheetOf(input)) {
        return;
    }
    if (input.matches("[data-sc-med-item-field]")) {
        saveItemField(input);
    } else if (input.matches("[data-sc-med-set]")) {
        savePlayerField(input);
    }
});

// Enter in a one-line field saves it (change) without submitting anything.
document.addEventListener("keydown", (ev) => {
    const input = ev.target;
    if (
        ev.key === "Enter" &&
        input instanceof HTMLInputElement &&
        input.type === "text" &&
        input.matches("[data-sc-med-item-field], [data-sc-med-set]") &&
        sheetOf(input)
    ) {
        ev.preventDefault();
        input.blur();
    }
});

// ----------------------------------------------------------------- delete
document.addEventListener("click", async (ev) => {
    const button = ev.target.closest && ev.target.closest("[data-sc-med-item-delete]");
    const sheet = button && sheetOf(button);
    if (!sheet) {
        return;
    }
    ev.preventDefault();
    const card = button.closest("[data-sc-med-item]");
    button.disabled = true;
    button.blur(); // a focused element pins its read fragment (#1641)
    try {
        const result = await scFetch(`/my/app/medical/item/${button.dataset.scMedItemDelete}/delete`, {
            method: "POST",
            toast: false,
        });
        if (card) {
            // The card being edited would hold the list's refresh: gone now.
            const list = card.parentElement;
            card.remove();
            if (list && !list.querySelector("[data-sc-med-item]")) {
                list.hidden = true;
            }
        }
        announce(sheet, result);
    } catch (error) {
        button.disabled = false;
        showError(card, messageOf(error));
    }
});
