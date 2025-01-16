/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { Component } from "@odoo/owl";

export class OpenWebUIAction extends Component {
    static template = "openwebui_integration.ClientAction";
    
    setup() {
        super.setup();
        this.state = {
            openwebui_enabled: false,
            openwebui_model: '',
            openwebui_api_url: ''
        };
        this.loadCompanyConfig();
    }

    async loadCompanyConfig() {
        const company = await this.env.services.orm.read(
            'res.company',
            [session.company_id],
            ['openwebui_enabled', 'openwebui_api_url', 'openwebui_model']
        );
        this.state = company[0];
    }
}

registry.category("actions").add("openwebui_action", OpenWebUIAction);
