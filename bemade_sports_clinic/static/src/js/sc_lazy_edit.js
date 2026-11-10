/*
 * Task 1736 r1 (owner 2026-11-01) — lazy edit views of the app shell.
 *
 * An activity card is edited in place like the other cards, but a list can
 * hold a hundred of them (and /my/activities lists each twice: « All » and
 * its state's tab). Its edit fields (sc_autosave_field islands) are
 * therefore rendered inside an inert <template data-sc-lazy-edit> of the
 * edit view ([data-sc-lazy-edit-host]) and mounted on the card's FIRST
 * pencil tap: sc_app_ui.js's setCardEditing dispatches « sc:edit-view-open »
 * on the edit view, this interaction (one, on the shell root) moves the
 * template's content into the edit view and starts the public interactions
 * on it — the core PublicComponentInteraction mounts the islands exactly as
 * for a server-rendered card. Once mounted, the fields stay.
 */
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

export class ScLazyEdit extends Interaction {
    static selector = ".o_sc_app[data-pk-app-shell]";

    start() {
        this.addListener(this.el, "sc:edit-view-open", (ev) => this.mountLazy(ev.target));
    }

    mountLazy(target) {
        const host = target && target.closest && target.closest("[data-sc-lazy-edit-host]");
        if (!host) {
            return;
        }
        const template = host.querySelector(":scope > template[data-sc-lazy-edit]");
        if (!template) {
            return; // already mounted
        }
        const content = document.importNode(template.content, true).firstElementChild;
        template.remove();
        if (content) {
            // Not removed if this interaction is ever stopped: the islands
            // belong to the card from now on.
            this.insert(content, host, "afterbegin", false);
            host.dataset.scLazyMounted = "1";
        }
    }
}

registry.category("public.interactions").add("bemade_sports_clinic.sc_lazy_edit", ScLazyEdit);
