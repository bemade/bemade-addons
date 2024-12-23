/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

class CycleProductPartnerListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    async ProcessHistoryButton() {
        try {
            await this.orm.call("itch.cycle.product.partner", "populate_from_past_orders", []);
            this.notification.add("L'action a été exécutée avec succès.", {
                type: "success",
            });
        } catch (error) {
            this.notification.add(`Une erreur s'est produite : ${error.message}`, {
                type: "danger",
            });
        }
    }
}

registry.category("views").add("cycle_product_partner_list", {
    ...listView,
    Controller: CycleProductPartnerListController,
    buttonTemplate: "customer_itch_cycle.process_history_button_in_tree",
});