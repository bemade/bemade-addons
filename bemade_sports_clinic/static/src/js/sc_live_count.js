/*
 * Task 1540 review (2026-09-29) — live counters of the app shell.
 *
 * A server-rendered chip marked
 *   data-sc-live-count-url="/my/clinics/today/count"   (JSON: {count: N})
 *   data-sc-live-poll="20"                              (seconds, optional)
 * is refreshed in place — the same mechanism as the live clinic worklist
 * (sc_clinic_worklist.js): a poll every 20 s while the tab is visible,
 * through scFetch (toast: false); an error backs off (x2, up to 5 min), a
 * success resets the interval; a hidden tab stops polling and the poll
 * resumes at once when the tab is shown again. Inert outside .o_sc_app.
 *
 * The chip's text becomes the count and its tone follows it
 * (data-sc-live-tone-on when > 0, data-sc-live-tone-off at 0), exactly like
 * the first server render.
 */
import { scFetch } from "@bemade_sports_clinic/js/sc_fetch";

const MAX_BACKOFF = 300000;

class LiveCount {
    constructor(el) {
        this.el = el;
        this.url = el.dataset.scLiveCountUrl;
        this.base = (parseInt(el.dataset.scLivePoll, 10) || 20) * 1000;
        this.interval = this.base;
        this.timer = null;
        this.onVisibility = () => {
            if (document.visibilityState === "visible") {
                this.schedule(0);
            }
        };
        document.addEventListener("visibilitychange", this.onVisibility);
        this.schedule();
    }

    schedule(delay = this.interval) {
        clearTimeout(this.timer);
        this.timer = setTimeout(() => this.poll(), delay);
    }

    async poll() {
        if (!this.el.isConnected) {
            document.removeEventListener("visibilitychange", this.onVisibility);
            return;
        }
        if (document.visibilityState === "hidden") {
            return; // resumed by visibilitychange
        }
        try {
            const data = await scFetch(this.url, { toast: false });
            if (data && Number.isInteger(data.count)) {
                this.apply(data.count);
            }
            this.interval = this.base;
        } catch {
            this.interval = Math.min(this.interval * 2, MAX_BACKOFF);
        }
        this.schedule();
    }

    apply(count) {
        const el = this.el;
        const text = String(count);
        if (el.textContent !== text) {
            el.textContent = text;
        }
        const on = el.dataset.scLiveToneOn;
        const off = el.dataset.scLiveToneOff;
        if (on && off) {
            el.classList.toggle(`o_sc_chip_${on}`, count > 0);
            el.classList.toggle(`o_sc_chip_${off}`, count <= 0);
        }
    }
}

function start() {
    for (const el of document.querySelectorAll(".o_sc_app [data-sc-live-count-url]")) {
        if (!el.scLiveCount) {
            el.scLiveCount = new LiveCount(el);
        }
    }
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
} else {
    start();
}
