/*
 * Task 1542 (epic #1535) — the device draft store of the app shell.
 *
 * localStorage, namespaced by database + user id + record key:
 *   sc_draft:<db>:<uid>:<recordKey>  ->  {"value": ..., "writeDate": ..., "at": ms}
 * The db / uid come from the shell root (data-sc-db / data-sc-uid). Drafts of
 * ANOTHER user (shared device) are discarded when the shell loads, and every
 * draft is cleared on « Déconnexion » (sc_app_ui.js). Never used for health
 * data read from the server — only what the user typed and has not sent.
 */
const PREFIX = "sc_draft:";

function storage() {
    try {
        return window.localStorage;
    } catch {
        return null; // private mode / blocked storage: drafts are simply off
    }
}

function scope() {
    const app = document.querySelector(".o_sc_app[data-sc-uid]");
    if (!app || !app.dataset.scUid) {
        return null;
    }
    return `${PREFIX}${app.dataset.scDb || ""}:${app.dataset.scUid}:`;
}

function allKeys(store) {
    const keys = [];
    for (let i = 0; i < store.length; i++) {
        const key = store.key(i);
        if (key && key.startsWith(PREFIX)) {
            keys.push(key);
        }
    }
    return keys;
}

export function readDraft(recordKey) {
    const store = storage();
    const prefix = scope();
    if (!store || !prefix) {
        return null;
    }
    try {
        const raw = store.getItem(prefix + recordKey);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export function writeDraft(recordKey, draft) {
    const store = storage();
    const prefix = scope();
    if (!store || !prefix) {
        return false;
    }
    try {
        store.setItem(prefix + recordKey, JSON.stringify({ ...draft, at: Date.now() }));
        return true;
    } catch {
        return false;
    }
}

export function removeDraft(recordKey) {
    const store = storage();
    const prefix = scope();
    if (store && prefix) {
        try {
            store.removeItem(prefix + recordKey);
        } catch {
            // ignore
        }
    }
}

/** Drop every draft that does not belong to the current db + user. */
export function purgeForeignDrafts() {
    const store = storage();
    const prefix = scope();
    if (!store || !prefix) {
        return;
    }
    for (const key of allKeys(store)) {
        if (!key.startsWith(prefix)) {
            store.removeItem(key);
        }
    }
}

/** Logout: drop every draft on this device. */
export function clearAllDrafts() {
    const store = storage();
    if (!store) {
        return;
    }
    for (const key of allKeys(store)) {
        store.removeItem(key);
    }
}
