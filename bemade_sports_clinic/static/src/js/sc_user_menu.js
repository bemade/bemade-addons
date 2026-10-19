/*
 * Task 1606 — the app shell's user menu (« Paramètres », « Se déconnecter »).
 *
 * Two triggers, one per width: the rail footer (name + initials, laptop) and
 * the initials avatar at the right of the app bar (phone). Each is a
 * button[data-sc-user-menu-toggle][aria-haspopup="menu"] whose aria-controls
 * names its popup ([data-sc-user-menu-popup], rendered hidden).
 *
 * - tap / Enter / Space toggles; ArrowDown / ArrowUp on the trigger open it
 *   on the first / last item;
 * - in the menu: ArrowDown / ArrowUp (wrapping), Home / End move the focus;
 *   Escape closes and gives the focus back to the trigger; Tab closes;
 * - a tap outside closes it; opening one closes the other.
 *
 * The items are plain links: « Se déconnecter » keeps the logout route (and
 * sc_app_ui.js still clears the device drafts on it). Inert outside .o_sc_app.
 *
 * Task 1607: the list header's sort menu is the same kind of popup —
 * button[data-sc-menu-toggle] + [data-sc-menu-popup] whose items are
 * a[role="menuitemradio"] links (the checked one gets the focus on open).
 */

const TOGGLE = "[data-sc-user-menu-toggle], [data-sc-menu-toggle]";
const POPUP = "[data-sc-user-menu-popup], [data-sc-menu-popup]";
const ITEM = '[role="menuitem"], [role="menuitemradio"]';

function popupOf(toggle) {
    const id = toggle.getAttribute("aria-controls");
    return id ? document.getElementById(id) : null;
}

function itemsOf(popup) {
    return [...popup.querySelectorAll(ITEM)];
}

function close(toggle, { focus = false } = {}) {
    const popup = popupOf(toggle);
    if (popup) {
        popup.hidden = true;
    }
    toggle.setAttribute("aria-expanded", "false");
    if (focus) {
        toggle.focus();
    }
}

function closeAll(except) {
    for (const toggle of document.querySelectorAll(TOGGLE)) {
        if (toggle.getAttribute("aria-expanded") !== "true" || !toggle.closest(".o_sc_app")) {
            continue;
        }
        if (toggle !== except) {
            close(toggle);
        }
    }
}

function open(toggle, which = "first") {
    const popup = popupOf(toggle);
    if (!popup) {
        return;
    }
    closeAll(toggle);
    popup.hidden = false;
    toggle.setAttribute("aria-expanded", "true");
    const items = itemsOf(popup);
    const checked = items.find((item) => item.getAttribute("aria-checked") === "true");
    const target =
        which === "last" ? items[items.length - 1] : which === "first" && checked ? checked : items[0];
    if (target) {
        target.focus();
    }
}

function toggleOf(el) {
    const popup = el.closest(POPUP);
    return popup
        ? [...document.querySelectorAll(TOGGLE)].find(
              (toggle) => toggle.getAttribute("aria-controls") === popup.id
          ) || null
        : null;
}

document.addEventListener("click", (ev) => {
    if (!ev.target.closest || !ev.target.closest(".o_sc_app")) {
        closeAll();
        return;
    }
    const toggle = ev.target.closest(TOGGLE);
    if (toggle) {
        if (toggle.getAttribute("aria-expanded") === "true") {
            close(toggle);
        } else {
            open(toggle);
        }
        return;
    }
    const item = ev.target.closest(ITEM);
    if (item && item.closest(POPUP)) {
        return; // the link navigates
    }
    if (!ev.target.closest(POPUP)) {
        closeAll();
    }
});

document.addEventListener("keydown", (ev) => {
    const target = ev.target;
    if (!target || !target.closest) {
        return;
    }
    const toggle = target.closest(TOGGLE);
    if (toggle && toggle.closest(".o_sc_app")) {
        if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
            ev.preventDefault();
            open(toggle, ev.key === "ArrowUp" ? "last" : "first");
        } else if (ev.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
            ev.preventDefault();
            close(toggle, { focus: true });
        }
        return;
    }
    const item = target.closest(ITEM);
    if (!item || !item.closest(POPUP) || !item.closest(".o_sc_app")) {
        return;
    }
    const owner = toggleOf(item);
    if (!owner) {
        return;
    }
    const items = itemsOf(item.closest(POPUP));
    const index = items.indexOf(item);
    let next = null;
    switch (ev.key) {
        case "ArrowDown":
            next = items[(index + 1) % items.length];
            break;
        case "ArrowUp":
            next = items[(index - 1 + items.length) % items.length];
            break;
        case "Home":
            next = items[0];
            break;
        case "End":
            next = items[items.length - 1];
            break;
        case "Escape":
            ev.preventDefault();
            close(owner, { focus: true });
            return;
        case "Tab":
            close(owner);
            return;
        case " ":
            ev.preventDefault();
            item.click();
            return;
        default:
            return;
    }
    ev.preventDefault();
    if (next) {
        next.focus();
    }
});

// Crossing the laptop width (rotation, window resize) swaps the visible
// trigger: never leave the hidden one's popup open. (Not on every resize:
// a phone's toolbar collapsing on scroll fires those.)
const laptop = window.matchMedia && window.matchMedia("(min-width: 992px)");
if (laptop && laptop.addEventListener) {
    laptop.addEventListener("change", () => closeAll());
}
// Back / forward cache: a restored page shows the menu closed.
window.addEventListener("pageshow", () => closeAll());
