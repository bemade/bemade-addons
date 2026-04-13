/** @odoo-module **/

import {Many2OneField, m2oTupleFromData} from "@web/views/fields/many2one/many2one_field";
import {patch} from "@web/core/utils/patch";

patch(Many2OneField.prototype, {
    /**
     * The original Many2OneField already has a quickCreate method and an openConfirmationDialog method.
     * The quickCreate method directly updates the record, while openConfirmationDialog shows a dialog
     * before calling quickCreate.
     * 
     * We just need to modify the Many2XAutocompleteProps getter to use openConfirmationDialog
     * instead of quickCreate for the quickCreate property.
     */
    get Many2XAutocompleteProps() {
        const props = super.Many2XAutocompleteProps;
        
        // If quickCreate is defined, replace it with openConfirmationDialog
        if (props.quickCreate && this.openConfirmationDialog) {
            // Store the original quickCreate function
            const originalQuickCreate = props.quickCreate;
            
            // Replace with openConfirmationDialog
            props.quickCreate = (name) => this.openConfirmationDialog(name);
        }
        
        return props;
    },
});
