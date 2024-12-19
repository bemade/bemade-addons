/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

class CycleProductPartnerListController extends ListController {
    setup() {
        super.setup();
        this.orm = this.env.services.orm; // Service ORM pour effectuer des appels RPC
    }

    async ProcessHistoryButton() {
        try {
            // Appel RPC via le service ORM
            await this.orm.call("itch.cycle.product.partner", "populate_from_past_orders", []);
            this.displayNotification({
                type: "success",
                message: "L'action a été exécutée avec succès.",
            });
        } catch (error) {
            this.displayNotification({
                type: "danger",
                message: `Une erreur s'est produite : ${error.message}`,
            });
        }
    }
}

// Enregistrement de la vue personnalisée
registry.category("views").add("cycle_product_partner_list", {
    ...listView,
    Controller: CycleProductPartnerListController,
    buttonTemplate: "customer_itch_cycle.process_history_button_in_tree",
});