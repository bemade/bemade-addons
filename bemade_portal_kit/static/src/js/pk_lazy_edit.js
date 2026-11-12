/*
 * Lazy edit views of the app shell (moved to the kit by task 5370, P4b).
 *
 * A card edited in place whose list can hold many cards keeps its edit
 * fields (OWL islands) inside an inert <template data-pk-lazy-edit> of the
 * edit view's host ([data-pk-lazy-edit-host]), and mounts them on the
 * card's FIRST edit: the page's script dispatches « pk:edit-view-open »
 * (bubbling) from the edit view it opens; this interaction (one, on the
 * shell root) moves the template's content into the host and starts the
 * public interactions on it — the core PublicComponentInteraction mounts
 * the islands exactly as for a server-rendered card. The host is then
 * marked data-pk-lazy-mounted. Once mounted, the fields stay.
 */
import { registry } from "@web/core/registry";
import { Interaction } from "@web/public/interaction";

/** Take the lazy content of ``target``'s host out of its template, or null
 * (no host, or mounted already). */
export function takeLazyEdit(target) {
    const host = target && target.closest && target.closest("[data-pk-lazy-edit-host]");
    if (!host) {
        return null;
    }
    const template = host.querySelector(":scope > template[data-pk-lazy-edit]");
    if (!template) {
        return null; // already mounted
    }
    const content = document.importNode(template.content, true).firstElementChild;
    template.remove();
    return content ? { host, content } : null;
}

export class PkLazyEdit extends Interaction {
    static selector = ".o_pk_app[data-pk-app-shell]";

    start() {
        this.addListener(this.el, "pk:edit-view-open", (ev) => this.mountLazy(ev.target));
    }

    mountLazy(target) {
        const lazy = takeLazyEdit(target);
        if (lazy) {
            // Not removed if this interaction is ever stopped: the islands
            // belong to the card from now on.
            this.insert(lazy.content, lazy.host, "afterbegin", false);
            lazy.host.dataset.pkLazyMounted = "1";
        }
    }
}

registry.category("public.interactions").add("bemade_portal_kit.pk_lazy_edit", PkLazyEdit);
