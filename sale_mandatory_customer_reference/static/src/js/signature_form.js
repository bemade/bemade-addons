/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { SignatureForm } from "@portal/signature_form/signature_form";

/**
 * Core's onClickSubmit only restores the submit button when the server asks
 * for a refresh: on an ``{error: ...}`` result, or when the RPC throws, the
 * button stays disabled with its spinner and the customer has to reload the
 * page. Restore it and surface the message instead.
 */
patch(SignatureForm.prototype, {
    async onClickSubmit() {
        try {
            await super.onClickSubmit(...arguments);
        } catch (error) {
            this.state.error =
                (error.data && error.data.message) || error.message || String(error);
            this.state.success = false;
        }
        if (this.state.error) {
            this._restoreSubmitButton();
        }
    },

    _restoreSubmitButton() {
        const button = this.rootRef.el && this.rootRef.el.querySelector(".o_portal_sign_submit");
        if (!button) {
            return;
        }
        button.classList.remove("o_btn_loading", "disabled", "pe-none");
        button.disabled = false;
        button.querySelectorAll(".fa-spin").forEach((el) => el.remove());
        if (!button.querySelector(".fa-check")) {
            const icon = document.createElement("i");
            icon.className = "fa fa-check me-1";
            button.prepend(icon);
        }
    },
});
