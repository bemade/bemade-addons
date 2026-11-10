/*
 * Task 1726 — the shared switch. Task 5197 (P2): moved from
 * bemade_sports_clinic (sc_switch.js) to the portal kit; the global is now
 * window.pkSwitchSync.
 *
 * The switch IS a checkbox (<input type="checkbox" role="switch">), so the
 * forms post what they posted before and Space toggles it natively. This
 * hook only:
 *   - keeps aria-checked in sync with the checked state;
 *   - enables the « off » hidden twin (sw_off) while the switch is off, so
 *     the form posts exactly ONE value;
 *   - submits the form of a switch marked data-pk-switch-submit (the
 *     Paramètres preferences: a switch has no submit button).
 * Every other behaviour (autosubmit filters, fetch forms, autosave) stays
 * with the script that owned the former checkbox.
 */
(function () {
    "use strict";

    function syncSwitch(input) {
        input.setAttribute("aria-checked", input.checked ? "true" : "false");
        const row = input.closest(".o_sc_switch");
        const twin = row && row.querySelector("input[data-pk-switch-off]");
        if (twin) {
            twin.disabled = input.checked;
        }
    }

    function isSwitch(el) {
        return el && el.matches && el.matches('input[type="checkbox"][role="switch"]');
    }

    document.addEventListener(
        "change",
        (ev) => {
            const input = ev.target;
            if (!isSwitch(input)) {
                return;
            }
            syncSwitch(input);
            if (input.hasAttribute("data-pk-switch-submit") && input.form) {
                if (input.form.requestSubmit) {
                    input.form.requestSubmit();
                } else {
                    input.form.submit();
                }
            }
        },
        true
    );

    // A form reset puts the switches back: their aria-checked follows.
    document.addEventListener(
        "reset",
        (ev) => {
            const form = ev.target;
            setTimeout(() => {
                form.querySelectorAll('input[role="switch"]').forEach(syncSwitch);
            });
        },
        true
    );

    window.pkSwitchSync = syncSwitch;
})();
