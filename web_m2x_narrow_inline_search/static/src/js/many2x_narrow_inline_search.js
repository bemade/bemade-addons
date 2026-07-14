/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { hasTouch } from "@web/core/browser/feature_detection";
import { Many2XAutocomplete } from "@web/views/fields/relational_utils";
import { SelectCreateDialog } from "@web/views/view_dialogs/select_create_dialog";

/**
 * Patch 1 — keep the inline autocomplete on a merely-narrow desktop window.
 *
 * Stock `web.Many2XAutocomplete` renders a read-only input that opens the search
 * dialog whenever `env.isSmall` (a pure viewport-width test) is true. That means
 * simply narrowing a desktop browser window loses the fast inline dropdown. We
 * expose a getter that additionally requires a real touch device — the same
 * discriminator core already uses for the selection field's bottom sheet
 * (`selection_field.js`: `this.env.isSmall && hasTouch()`). The template
 * extension gates the dialog input on this getter, so a narrow non-touch window
 * falls through to the normal `<AutoComplete>` branch.
 */
patch(Many2XAutocomplete.prototype, {
    get useMobileSearchInput() {
        return this.env.isSmall && hasTouch() && this.props.dropdown;
    },
});

/**
 * Patch 2 — open the relational search dialog list-first on small screens.
 *
 * Stock `SelectCreateDialog.viewProps` picks `kanban` when `env.isSmall`, else
 * `list`. Kanban is the only branch that depends on the small screen, so we
 * post-process the original props: whenever the dialog would have opened in
 * kanban (i.e. on a small screen), re-shape it as a list — denser and easier to
 * scan — mirroring the wide-screen defaults (`allowSelectors` / `allowOpenAction`)
 * and dropping the kanban-only `forceGlobalClick`.
 */
patch(SelectCreateDialog.prototype, {
    get viewProps() {
        const props = super.viewProps;
        if (props.type === "kanban") {
            delete props.forceGlobalClick;
            props.type = "list";
            props.allowSelectors = this.props.multiSelect;
            props.allowOpenAction = false;
        }
        return props;
    },
});
