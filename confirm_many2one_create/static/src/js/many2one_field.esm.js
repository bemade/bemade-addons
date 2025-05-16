/** @odoo-module **/

import {Many2OneField} from "@web/views/fields/many2one/many2one_field";
import {patch} from "@web/core/utils/patch";
import {_t} from "@web/core/l10n/translation";
import {Dialog} from "@web/core/dialog/dialog";
import {Component, markup} from "@odoo/owl";

// Create a custom confirmation dialog component
class CreateConfirmationDialog extends Component {
    static template = "web.Many2OneField.CreateConfirmationDialog";
    static components = {Dialog};

    get title() {
        return _t("New: %s", this.props.name);
    }

    get dialogContent() {
        return markup(
            _t(
                "Create <strong>%s</strong> as a new %s?",
                this.props.value,
                this.props.name
            )
        );
    }

    async onCreate() {
        await this.props.create();
        this.props.close();
    }
}

patch(Many2OneField.prototype, {
    setup() {
        // Call the original setup method
        super.setup();
        
        // Store the original quickCreate function
        const originalQuickCreate = this.quickCreate;
        
        // Replace the quickCreate function with our own implementation
        if (originalQuickCreate) {
            // Save the original quickCreate function
            this._originalQuickCreate = originalQuickCreate;
            
            // Override quickCreate to show a confirmation dialog
            this.quickCreate = async (name) => {
                this.state.isFloating = false;
                
                return new Promise((resolve, reject) => {
                    this.addDialog(CreateConfirmationDialog, {
                        name: this.string,
                        value: name,
                        create: async () => {
                            try {
                                // Call the original quickCreate function
                                await this._originalQuickCreate(name);
                                resolve();
                            } catch (e) {
                                reject(e);
                            }
                        },
                    });
                });
            };
        }
    },
});
