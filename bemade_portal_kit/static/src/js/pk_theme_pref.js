/*
 * Task 5345 (kit P3c2) — the theme preference, switched in place.
 *
 * The app layout's theme toggle and a consumer's appearance controls are
 * ordinary POST forms (form[data-pk-pref]) to the consumer's preference
 * route, which redirects back: they work without this script. With it, the
 * post goes through fetch (Accept: application/json) and the answer's
 * ``pk_theme`` (dark | light) is applied in place, no reload:
 *
 * - the shell root's data-pk-theme and the body's o_pk_app_body_<theme>;
 * - <meta name="theme-color">: data-pk-theme-color-<theme> of the root
 *   (the layout writes the brand's colours there);
 * - the toggles (button[data-pk-theme-toggle]) offer the other theme;
 *   buttons carrying data-pk-theme-value + aria-pressed follow the theme;
 *   a switch input[data-pk-theme-switch] is on in the dark theme
 *   (window.pkSwitchSync keeps its aria-checked and « off » twin).
 *
 * A failed fetch falls back to the plain post. Inert outside .o_pk_app.
 * Export: applyTheme(app, theme).
 */

const THEMES = ["dark", "light"];

export function applyTheme(app, theme) {
    if (!app || !THEMES.includes(theme)) {
        return;
    }
    app.setAttribute("data-pk-theme", theme);
    document.body.classList.remove("o_pk_app_body_dark", "o_pk_app_body_light");
    document.body.classList.add(`o_pk_app_body_${theme}`);
    const color = app.getAttribute(`data-pk-theme-color-${theme}`);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta && color) {
        meta.setAttribute("content", color);
    }
    for (const button of app.querySelectorAll("button[data-pk-theme-toggle]")) {
        button.value = theme === "light" ? "dark" : "light";
    }
    for (const button of app.querySelectorAll("button[data-pk-theme-value][aria-pressed]")) {
        button.setAttribute("aria-pressed", button.dataset.pkThemeValue === theme ? "true" : "false");
    }
    for (const input of app.querySelectorAll("input[data-pk-theme-switch]")) {
        input.checked = theme === "dark";
        if (window.pkSwitchSync) {
            window.pkSwitchSync(input);
        } else {
            input.setAttribute("aria-checked", input.checked ? "true" : "false");
        }
    }
}

function plainPost(form, submitter) {
    // form.submit() drops the clicked button's name / value: carry it.
    if (submitter && submitter.name) {
        const hidden = document.createElement("input");
        hidden.type = "hidden";
        hidden.name = submitter.name;
        hidden.value = submitter.value;
        form.appendChild(hidden);
    }
    form.submit();
}

function onSubmit(ev) {
    const form = ev.target;
    if (!form || !form.matches || !form.matches("form[data-pk-pref]")) {
        return;
    }
    const app = form.closest(".o_pk_app");
    if (!app || !window.fetch || !window.FormData) {
        return;
    }
    const submitter = ev.submitter || null;
    let data;
    try {
        data = submitter ? new FormData(form, submitter) : new FormData(form);
    } catch {
        return; // an old browser without FormData(form, submitter): the plain post
    }
    ev.preventDefault();
    fetch(form.action, {
        method: "POST",
        body: data,
        credentials: "same-origin",
        headers: { Accept: "application/json" },
    })
        .then((resp) => {
            if (!resp.ok) {
                throw new Error(`pref ${resp.status}`);
            }
            return resp.json();
        })
        .then((prefs) => {
            if (prefs && prefs.pk_theme) {
                applyTheme(app, prefs.pk_theme);
            }
        })
        .catch(() => plainPost(form, submitter));
}

document.addEventListener("submit", onSubmit);
