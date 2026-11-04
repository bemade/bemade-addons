/**
 * Task 1411: the clinic dossier's quick match / practice status form.
 *
 * Progressive enhancement only — the server validates the combination
 * (sports.patient.constrain_match_and_practice_status, mirrored in
 * /my/player/<id>/quick) and bounces an invalid pair back with an inline
 * error. This script merely snaps the selects to the only valid pairing so
 * the therapist rarely hits that error:
 *  - Match = Yes  ⇒ Practice snaps to Yes (a player who can play can practice);
 *  - Practice ≠ Yes ⇒ Match snaps to No.
 * Vanilla, self-contained, in the style of the addon's other portal scripts.
 */
(function () {
    "use strict";

    function bind(form) {
        if (form.getAttribute("data-quick-status-bound")) {
            return;
        }
        form.setAttribute("data-quick-status-bound", "1");
        var match = form.querySelector("select[name='match_status']");
        var practice = form.querySelector("select[name='practice_status']");
        if (!match || !practice) {
            return;
        }
        match.addEventListener("change", function () {
            if (match.value === "yes" && practice.value !== "yes") {
                practice.value = "yes";
            }
        });
        practice.addEventListener("change", function () {
            if (practice.value !== "yes" && match.value === "yes") {
                match.value = "no";
            }
        });
    }

    function init() {
        var forms = document.querySelectorAll("form.o_sc_clinic_quick_status");
        Array.prototype.forEach.call(forms, bind);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
