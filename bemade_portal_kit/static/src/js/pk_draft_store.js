/*
 * Task 1542 (epic #1535) — the device draft store of the app shell.
 *
 * localStorage, namespaced by database + user id + record key:
 *   pk_draft:<db>:<uid>:<recordKey>  ->  {"value": ..., "writeDate": ..., "at": ms}
 * The db / uid come from the shell root (data-pk-db / data-pk-uid). Drafts of
 * ANOTHER user (shared device) are discarded when the shell loads, and every
 * draft is cleared on « Déconnexion » (the consumer calls clearAllDrafts).
 * Never used for health data read from the server — only what the user typed
 * and has not sent.
 *
 * Task 5198 (P3a): the prefix was « sc_draft: » before. A draft stored under
 * the old prefix is read once, moved under the new one and removed, so a draft
 * typed before the upgrade survives it.
 * Old-prefix fallback: remove once Fit Crew has run P3a for a release.
 */
export const DRAFT_PREFIX = "pk_draft:";
const OLD_DRAFT_PREFIX = "sc_draft:"; // old-prefix fallback (task 5198)
const PREFIXES = [DRAFT_PREFIX, OLD_DRAFT_PREFIX];

function storage() {
    try {
        return window.localStorage;
    } catch {
        return null; // private mode / blocked storage: drafts are simply off
    }
}

/** ``<db>:<uid>:`` of the current shell, or null outside the shell. */
function scope() {
    const app = document.querySelector(".o_sc_app[data-pk-uid]");
    if (!app || !app.dataset.pkUid) {
        return null;
    }
    return `${app.dataset.pkDb || ""}:${app.dataset.pkUid}:`;
}

/** Every draft key on this device (both prefixes). */
function allKeys(store) {
    const keys = [];
    for (let i = 0; i < store.length; i++) {
        const key = store.key(i);
        if (key && PREFIXES.some((prefix) => key.startsWith(prefix))) {
            keys.push(key);
        }
    }
    return keys;
}

function remove(store, key) {
    try {
        store.removeItem(key);
    } catch {
        // ignore
    }
}

/** Old-prefix fallback: move one old draft under the new key (new one wins). */
function migrate(store, ownScope, recordKey) {
    const oldKey = OLD_DRAFT_PREFIX + ownScope + recordKey;
    const raw = store.getItem(oldKey);
    if (raw === null) {
        return;
    }
    const newKey = DRAFT_PREFIX + ownScope + recordKey;
    if (store.getItem(newKey) === null) {
        store.setItem(newKey, raw);
    }
    store.removeItem(oldKey);
}

export function readDraft(recordKey) {
    const store = storage();
    const ownScope = scope();
    if (!store || !ownScope) {
        return null;
    }
    try {
        migrate(store, ownScope, recordKey);
        const raw = store.getItem(DRAFT_PREFIX + ownScope + recordKey);
        return raw ? JSON.parse(raw) : null;
    } catch {
        return null;
    }
}

export function writeDraft(recordKey, draft) {
    const store = storage();
    const ownScope = scope();
    if (!store || !ownScope) {
        return false;
    }
    try {
        store.setItem(DRAFT_PREFIX + ownScope + recordKey, JSON.stringify({ ...draft, at: Date.now() }));
        remove(store, OLD_DRAFT_PREFIX + ownScope + recordKey);
        return true;
    } catch {
        return false;
    }
}

export function removeDraft(recordKey) {
    const store = storage();
    const ownScope = scope();
    if (store && ownScope) {
        for (const prefix of PREFIXES) {
            remove(store, prefix + ownScope + recordKey);
        }
    }
}

/**
 * Drop every draft that does not belong to the current db + user; this
 * user's old-prefix drafts are moved under the new prefix.
 */
export function purgeForeignDrafts() {
    const store = storage();
    const ownScope = scope();
    if (!store || !ownScope) {
        return;
    }
    for (const key of allKeys(store)) {
        if (key.startsWith(DRAFT_PREFIX + ownScope)) {
            continue;
        }
        if (key.startsWith(OLD_DRAFT_PREFIX + ownScope)) {
            try {
                migrate(store, ownScope, key.slice((OLD_DRAFT_PREFIX + ownScope).length));
            } catch {
                remove(store, key);
            }
            continue;
        }
        remove(store, key);
    }
}

/** Logout: drop every draft on this device. */
export function clearAllDrafts() {
    const store = storage();
    if (!store) {
        return;
    }
    for (const key of allKeys(store)) {
        remove(store, key);
    }
}

/**
 * Task 1539: drop this user's drafts whose record key starts with
 * ``keyPrefix`` (a NEW injury / note once « Créer » / « Ajouter » landed).
 */
export function removeDraftsWithPrefix(keyPrefix) {
    const store = storage();
    const ownScope = scope();
    if (!store || !ownScope || !keyPrefix) {
        return;
    }
    for (const key of allKeys(store)) {
        if (PREFIXES.some((prefix) => key.startsWith(prefix + ownScope + keyPrefix))) {
            remove(store, key);
        }
    }
}
