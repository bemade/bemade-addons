/*
 * Task 1640 — date inputs take a 4-digit year.
 *
 * A native <input type="date"> without ``max`` lets Chrome type a 6-digit
 * year (« 202610-10-10 ») and never move on to the month; the value then
 * fails on save. Chrome sizes the year segment from ``max``: with a max year
 * of 9999 the 5th digit moves to the month.
 *
 * - DATE_BOUNDS: the default min / max per input type (date, datetime-local);
 * - isValidDateValue(type, value): an empty or in-range ISO value;
 * - stampDateBounds(root): set the defaults on the date / datetime-local
 *   inputs under ``root`` that have no min / max of their own (an existing
 *   bound — min=today on a deadline, max=today on « Résoudre » — is never
 *   overridden). Runs on load, after a fragment swap (``sc:fragments``),
 *   after a lazy body is injected (``sc:lazy-loaded``) and, as a safety net
 *   for any other injected input, on focus (capture phase). App shell AND
 *   legacy portal pages (the same frontend bundle).
 */

export const DATE_BOUNDS = {
    date: { min: "1900-01-01", max: "9999-12-31" },
    "datetime-local": { min: "1900-01-01T00:00", max: "9999-12-31T23:59" },
};

const MIN_YEAR = 1900;
const MAX_YEAR = 9999;
const DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;
const DATETIME_RE = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?$/;

function validDay(year, month, day) {
    if (year < MIN_YEAR || year > MAX_YEAR || month < 1 || month > 12 || day < 1) {
        return false;
    }
    return day <= new Date(Date.UTC(year, month, 0)).getUTCDate();
}

/**
 * True for an empty value or a well-formed in-range ISO date (``date`` /
 * ``date_na``, where "na" is valid too) or date-time (``datetime-local``).
 * Other types are not checked.
 */
export function isValidDateValue(type, value) {
    const text = value === null || value === undefined ? "" : String(value).trim();
    if (!text) {
        return true;
    }
    if (type === "date" || type === "date_na") {
        if (type === "date_na" && text === "na") {
            return true;
        }
        const m = DATE_RE.exec(text);
        return Boolean(m) && validDay(+m[1], +m[2], +m[3]);
    }
    if (type === "datetime-local") {
        const m = DATETIME_RE.exec(text);
        return Boolean(m) && validDay(+m[1], +m[2], +m[3]) && +m[4] < 24 && +m[5] < 60;
    }
    return true;
}

const SELECTOR = 'input[type="date"], input[type="datetime-local"]';

function stampOne(input) {
    const bounds = DATE_BOUNDS[input.type];
    if (!bounds) {
        return;
    }
    if (!input.hasAttribute("min")) {
        input.setAttribute("min", bounds.min);
    }
    if (!input.hasAttribute("max")) {
        input.setAttribute("max", bounds.max);
    }
}

export function stampDateBounds(root = document) {
    if (!root) {
        return;
    }
    if (root.matches && root.matches(SELECTOR)) {
        stampOne(root);
    }
    if (root.querySelectorAll) {
        for (const input of root.querySelectorAll(SELECTOR)) {
            stampOne(input);
        }
    }
}

if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => stampDateBounds());
    } else {
        stampDateBounds();
    }
    document.addEventListener("sc:fragments", () => stampDateBounds());
    document.addEventListener("sc:lazy-loaded", (ev) => stampDateBounds(ev.target));
    document.addEventListener(
        "focusin",
        (ev) => {
            if (ev.target && ev.target.matches && ev.target.matches(SELECTOR)) {
                stampOne(ev.target);
            }
        },
        true
    );
}
