/** @odoo-module **/

import { DocumentsKanbanController } from "@documents/views/kanban/documents_kanban_controller";
import { DocumentsKanbanModel } from "@documents/views/kanban/documents_kanban_model";
import { DocumentsListController } from "@documents/views/list/documents_list_controller";
import { DocumentsListModel } from "@documents/views/list/documents_list_model";
import { _t } from "@web/core/l10n/translation";
import { patch } from "@web/core/utils/patch";

/**
 * Documents-side "Link to Record" entry point (task #3678 defect 1).
 *
 * The enterprise Documents app does NOT render the standard ActionMenus
 * component, so a server action bound via `binding_model_id` /
 * `binding_view_types` never surfaces in the Documents UI. We therefore have to
 * add the entry explicitly.
 *
 * In 18.0 the app hard-coded its buttons in the `documents.ControlPanel`
 * template, so we injected ours with a `t-inherit` xpath anchored on the
 * "Duplicate" button. In 19.0 that template no longer holds any action button:
 * the control panel just renders `<DocumentsAction/>`, which builds its buttons
 * from the dict returned by the controller's `getTopBarActionMenuItems()`
 * (see enterprise/documents/static/src/views/documents_controller_mixin.js).
 * The old xpath matched nothing and made the whole Documents app crash at
 * template compilation ("Element ... cannot be located in element tree").
 *
 * So we now extend that dict instead of patching a template — no xpath, hence
 * nothing left to break when the upstream markup changes again. The action
 * itself lives on the model, next to the stock `onDuplicate` / `onShare`
 * handlers it sits beside in the UI.
 *
 * Both patches are built by a factory rather than declared once and reused:
 * `patch()` takes ownership of the extension object it is given
 * (`Object.setPrototypeOf(extension, skeleton)`, web/core/utils/patch.js), so
 * passing one literal to two targets makes the second call rewrite the first
 * one's `super` chain -- which breaks the controllers at render time.
 */

const makeModelPatch = () => ({
    /**
     * True when every selected record is a real binary document with an
     * attachment. A document can now be linked to many records (task #3678),
     * so -- unlike the stock guard -- already-linked documents
     * (res_model !== 'documents.document') remain eligible too.
     */
    get canLinkToRecord() {
        const records = this.targetRecords;
        return (
            this.documentService.userIsInternal &&
            this.env.searchModel.getSelectedFolder()?.id !== "TRASH" &&
            records.length > 0 &&
            records.every((r) => r.data.type === "binary" && r.data.attachment_id)
        );
    },

    /**
     * Open the stock "Link to Record" wizard on the selected documents.
     *
     * Calls `documents.document.action_link_to_record()`, which this module
     * overrides (models/documents_document.py) to drop the stock
     * "already linked" refusal; the wizard then offers a model picker limited
     * to mail.thread models, followed by a record picker.
     */
    async onLinkToRecord() {
        const documentIds = this.targetRecords.map((record) => record.data.id);
        if (!documentIds.length) {
            return;
        }
        const action = await this.orm.call("documents.document", "action_link_to_record", [
            documentIds,
        ]);
        if (action) {
            await this.action.doAction(action, {
                onClose: () => this._notifyChange(),
            });
        }
    },
});

const makeControllerPatch = () => ({
    /**
     * `getStaticActionMenuItems` folds these entries into the cog dropdown on
     * small screens, so adding ours here covers both layouts.
     */
    getTopBarActionMenuItems() {
        return {
            ...super.getTopBarActionMenuItems(),
            bemade_link_to_record: {
                // Between "Download" (50) and "Share" (51) upstream, so our
                // entry lands last in that group rather than splitting them.
                isAvailable: () => this.model.canLinkToRecord,
                sequence: 52,
                description: _t("Link to Record"),
                icon: "fa fa-link",
                callback: () => this.model.onLinkToRecord(),
                groupNumber: 1,
            },
        };
    },
});

patch(DocumentsListModel.prototype, makeModelPatch());
patch(DocumentsKanbanModel.prototype, makeModelPatch());
patch(DocumentsListController.prototype, makeControllerPatch());
patch(DocumentsKanbanController.prototype, makeControllerPatch());
