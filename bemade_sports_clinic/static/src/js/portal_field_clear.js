/*
 * Task 1384 — one-tap "Effacer" (Clear) for long-text portal fields.
 *
 * Vanilla JS (matches the other plain-JS portal helpers in this module —
 * jquery_scrolling_polyfill.js, website_toc_safety_patch.js — NOT OWL).
 *
 * A single delegated listener on `document` handles every Clear control
 * (`.o_sc_field_clear[data-clear-target]`) rendered by the
 * `portal_field_label_clear` QWeb macro, so no per-field wiring is needed.
 * Activating a control empties the referenced <textarea> and fires `input`
 * + `change` so any dependent UI (char counters, autosize) reacts. The value
 * is only persisted on the form's normal Save.
 */
(function () {
    "use strict";

    function clearTarget(control) {
        if (!control || !control.getAttribute) {
            return;
        }
        var targetId = control.getAttribute("data-clear-target");
        if (!targetId) {
            return;
        }
        var field = document.getElementById(targetId);
        if (!field) {
            return;
        }
        field.value = "";
        // Notify any listeners (autosize, counters, validation) and refocus.
        field.dispatchEvent(new Event("input", { bubbles: true }));
        field.dispatchEvent(new Event("change", { bubbles: true }));
        try {
            field.focus();
        } catch (_e) {
            // focus is best-effort; ignore if the element can't take it.
        }
    }

    document.addEventListener("click", function (ev) {
        var control = ev.target.closest && ev.target.closest(".o_sc_field_clear[data-clear-target]");
        if (!control) {
            return;
        }
        ev.preventDefault();
        clearTarget(control);
    });

    document.addEventListener("keydown", function (ev) {
        if (ev.key !== "Enter" && ev.key !== " " && ev.key !== "Spacebar") {
            return;
        }
        var control = ev.target.closest && ev.target.closest(".o_sc_field_clear[data-clear-target]");
        if (!control) {
            return;
        }
        ev.preventDefault();
        clearTarget(control);
    });
})();
