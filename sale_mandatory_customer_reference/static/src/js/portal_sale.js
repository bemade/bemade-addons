/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";
import { rpc } from "@web/core/network/rpc";

publicWidget.registry.SalePortalReference = publicWidget.Widget.extend({
    selector: '.o_portal_sale_reference',
    events: {
        'change input[name="client_order_ref"]': '_onReferenceChange',
    },

    /**
     * @override
     */
    start: function () {
        this.orderId = this.el.dataset.orderId;
        this.accessToken = this.el.dataset.accessToken;
        return this._super.apply(this, arguments);
    },

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Show a notification message
     * @private
     */
    _showNotification(message, type = 'success') {
        const alertClass = type === 'success' ? 'alert-success' : 'alert-danger';
        const $notification = $('<div>', {
            class: `alert ${alertClass} alert-dismissible fade show`,
            role: 'alert',
            text: message
        }).append($('<button>', {
            type: 'button',
            class: 'btn-close',
            'data-bs-dismiss': 'alert',
            'aria-label': 'Close'
        }));

        // Remove any existing alerts
        this.$('.alert').remove();

        // Add the new alert before the input
        this.$('input[name="client_order_ref"]').before($notification);

        // Auto-hide after 5 seconds
        setTimeout(() => {
            $notification.alert('close');
        }, 5000);
    },

    /**
     * Save the reference when it changes
     * @private
     */
    async _saveReference(reference) {
        try {
            const params = { reference };
            if (this.accessToken) {
                params.access_token = this.accessToken;
            }
            
            const result = await rpc('/my/orders/' + this.orderId + '/update_reference', params);

            if (result.error) {
                this._showNotification(_t(result.error), 'danger');
                return false;
            }

            this._showNotification(_t("Reference updated successfully"));
            return true;
        } catch (error) {
            console.error('RPC error:', error);
            this._showNotification(_t("Failed to save your reference. Please try again."), 'danger');
            return false;
        }
    },

    //--------------------------------------------------------------------------
    // Handlers
    //--------------------------------------------------------------------------

    /**
     * @private
     */
    async _onReferenceChange(ev) {
        const reference = ev.target.value;
        if (!this.orderId) {
            this._showNotification(_t("Could not determine the order ID"), 'danger');
            return;
        }
        await this._saveReference(reference);
    },
});

export default publicWidget.registry.SalePortalReference;
