/*
 * Task 1654 — the medical popups' life-threatening items (inert outside
 * .o_sc_app): form[data-sc-critical-add] adds one, a
 * [data-sc-critical-delete] button removes one. Each answer is announced as a
 * save of the family's level (« sc:saved »), so the level field, EpiPen, the
 * pills, the cards and the item list follow in place.
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

function announce(patientId, result) {
    document.dispatchEvent(
        new CustomEvent("sc:saved", {
            // « source »: the level island takes the answer as a twin's save.
            detail: {
                model: "sports.patient",
                recordId: Number(patientId),
                field: result.field,
                result,
                source: "critical-items",
            },
        })
    );
}

function showError(form, message) {
    const box = form && form.querySelector("[data-sc-critical-error]");
    if (box) {
        box.textContent = message || "";
        box.hidden = !message;
    }
}

document.addEventListener(
    "submit",
    async (ev) => {
        const form = ev.target;
        if (!(form instanceof HTMLFormElement) || !form.matches("form[data-sc-critical-add]") || !form.closest(".o_sc_app")) {
            return;
        }
        ev.preventDefault();
        const button = form.querySelector('button[type="submit"]');
        const data = {
            patient_id: form.dataset.scPatient,
            family: form.dataset.scFamily,
            name: form.elements.name.value,
            action: form.elements.action ? form.elements.action.value : "",
            epipen: form.elements.epipen && form.elements.epipen.checked ? "1" : "",
        };
        button.disabled = true;
        showError(form, "");
        try {
            const result = await scFetch("/my/app/critical/add", { method: "POST", data, toast: false });
            form.reset();
            announce(form.dataset.scPatient, result);
        } catch (error) {
            showError(form, (error && error.payload && error.payload.message) || "");
        } finally {
            button.disabled = false;
        }
    },
    true
);

document.addEventListener("click", async (ev) => {
    const button = ev.target.closest && ev.target.closest("[data-sc-critical-delete]");
    if (!button || !button.closest(".o_sc_app")) {
        return;
    }
    ev.preventDefault();
    const sheet = button.closest("dialog");
    const form = sheet && sheet.querySelector("form[data-sc-critical-add]");
    button.disabled = true;
    button.blur(); // a focused element pins its read fragment (#1641)
    try {
        const result = await scFetch(`/my/app/critical/${button.dataset.scCriticalDelete}/delete`, {
            method: "POST",
            toast: false,
        });
        announce(form ? form.dataset.scPatient : 0, result);
    } catch (error) {
        button.disabled = false;
        showError(form, (error && error.payload && error.payload.message) || "");
    }
});
