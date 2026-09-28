/*
 * Task 1542 (epic #1535) — the app shell's ONE fetch helper.
 *
 * GET / POST, JSON or HTML, the CSRF token added to every POST, a timeout,
 * and an error toast hook: every failure dispatches « sc:fetch-error » on the
 * document (sc_app_ui.js shows the toast) unless called with toast: false.
 * POST bodies are form-encoded so Odoo's standard http CSRF check applies.
 *
 * Used by the shell only (lazy sheets, lazy rows, the autosave component).
 * The legacy page keeps its own portal_card_recent_changes.js /
 * portal_digest_history.js.
 */
export class ScFetchError extends Error {
    constructor(status, payload, reason) {
        super(reason || `HTTP ${status}`);
        this.name = "ScFetchError";
        this.status = status; // 0 = network error / timeout
        this.payload = payload;
        this.reason = reason || (status ? "http" : "network");
    }
}

export function csrfToken() {
    if (window.odoo && window.odoo.csrf_token) {
        return window.odoo.csrf_token;
    }
    const input = document.querySelector('input[name="csrf_token"]');
    return input ? input.value : "";
}

export function notifyFetchError(error) {
    document.dispatchEvent(new CustomEvent("sc:fetch-error", { detail: error }));
}

/**
 * @param {string} url
 * @param {Object} [options]
 * @param {"GET"|"POST"} [options.method]
 * @param {Object} [options.data] POST fields (form-encoded)
 * @param {"json"|"html"} [options.as] expected answer
 * @param {number} [options.timeout] ms
 * @param {boolean} [options.toast] dispatch sc:fetch-error on failure
 */
export async function scFetch(url, options = {}) {
    const { method = "GET", data = null, as = "json", timeout = 15000, toast = true } = options;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeout);
    const init = {
        method,
        credentials: "same-origin",
        signal: controller.signal,
        headers: {
            "X-Requested-With": "XMLHttpRequest",
            Accept: as === "json" ? "application/json" : "text/html",
        },
    };
    if (method !== "GET") {
        const body = new URLSearchParams();
        for (const [key, value] of Object.entries(data || {})) {
            body.set(key, value === null || value === undefined || value === false ? "" : value);
        }
        if (!body.has("csrf_token")) {
            body.set("csrf_token", csrfToken());
        }
        init.body = body;
    }
    try {
        const response = await fetch(url, init);
        const payload =
            as === "json" ? await response.json().catch(() => null) : await response.text();
        if (!response.ok) {
            throw new ScFetchError(response.status, payload);
        }
        return payload;
    } catch (err) {
        const error =
            err instanceof ScFetchError
                ? err
                : new ScFetchError(0, null, err && err.name === "AbortError" ? "timeout" : "network");
        if (toast) {
            notifyFetchError(error);
        }
        throw error;
    } finally {
        clearTimeout(timer);
    }
}
