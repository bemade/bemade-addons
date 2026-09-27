/*
 * Task 1538 (epic #1535) — portal app shell: instant preference switch.
 *
 * Vanilla JS, progressive enhancement only (matches the other plain-JS
 * portal helpers of this module). The theme toggle in the app bar and the
 * « Plus › Apparence / Navigation » controls are ordinary POST forms to
 * /my/app/pref (marked data-sc-pref) that redirect back — they work without
 * this script. With it, the post goes through fetch (JSON answer) and the
 * page switches in place: no reload for the theme, a reload for the
 * navigation mode (the app bar is server-rendered for it).
 *
 * Inert outside the shell: it only acts on forms inside .o_sc_app.
 */
(function () {
    "use strict";

    function applyTheme(app, theme) {
        app.setAttribute("data-sc-theme", theme);
        document.body.classList.remove("o_sc_app_body_dark", "o_sc_app_body_light");
        document.body.classList.add("o_sc_app_body_" + theme);
        var meta = document.querySelector('meta[name="theme-color"]');
        if (meta) {
            meta.setAttribute("content", theme === "light" ? "#243925" : "#120e12");
        }
        var toggles = app.querySelectorAll('.o_sc_theme_toggle button[name="sc_theme"]');
        toggles.forEach(function (button) {
            button.value = theme === "light" ? "dark" : "light";
        });
        var pressed = app.querySelectorAll('button[name="sc_theme"][aria-pressed]');
        pressed.forEach(function (button) {
            button.setAttribute("aria-pressed", button.value === theme ? "true" : "false");
        });
    }

    document.addEventListener("submit", function (ev) {
        var form = ev.target;
        if (!form || !form.matches || !form.matches("form[data-sc-pref]")) {
            return;
        }
        var app = form.closest(".o_sc_app");
        if (!app || !window.fetch || !window.FormData) {
            return;
        }
        var submitter = ev.submitter || null;
        var data;
        try {
            data = submitter ? new FormData(form, submitter) : new FormData(form);
        } catch (_err) {
            return; // old browser: FormData(form, submitter) unsupported — plain post
        }
        ev.preventDefault();
        fetch(form.action, {
            method: "POST",
            body: data,
            credentials: "same-origin",
            headers: { Accept: "application/json" },
        })
            .then(function (resp) {
                if (!resp.ok) {
                    throw new Error("pref " + resp.status);
                }
                return resp.json();
            })
            .then(function (prefs) {
                if (prefs.sc_nav_mode && prefs.sc_nav_mode !== app.getAttribute("data-sc-nav")) {
                    window.location.reload();
                    return;
                }
                if (prefs.sc_theme) {
                    applyTheme(app, prefs.sc_theme);
                }
            })
            .catch(function () {
                // Fall back to the no-JS path; form.submit() drops the
                // clicked button's name/value, so carry it in a hidden input.
                if (submitter && submitter.name) {
                    var hidden = document.createElement("input");
                    hidden.type = "hidden";
                    hidden.name = submitter.name;
                    hidden.value = submitter.value;
                    form.appendChild(hidden);
                }
                form.submit();
            });
    });
})();
