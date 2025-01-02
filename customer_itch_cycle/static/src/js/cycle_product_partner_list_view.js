/** @odoo-module **/

import { registry } from "@web/core/registry";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";
import { useService } from "@web/core/utils/hooks";

/**
 * Custom List Controller for Product/Partner Cycle Management
 * Extends standard list view to add history processing functionality
 */
class CycleProductPartnerListController extends ListController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    /**
     * Process historical sales data to update cycles
     * Shows notifications for processing status
     */
    async ProcessHistoryButton() {
        try {
            this.notification.add("Starting history processing...", {
                type: "info",
                sticky: false,
            });
            
            const result = await this.orm.call("itch.cycle.product.partner", "populate_from_past_orders", []);
            
            if (result && result.tag === 'display_notifications' && result.params.notifications) {
                for (const notif of result.params.notifications) {
                    this.notification.add(notif.params.message, {
                        type: notif.params.type,
                        sticky: notif.params.sticky,
                    });
                    await new Promise(resolve => setTimeout(resolve, 300));
                }
            }
            
            await this.model.load();
        } catch (error) {
            this.notification.add(`An error occurred: ${error.message}`, {
                type: "danger",
            });
        }
    }
}

// Register the custom list view for cycle product partner
registry.category("views").add("cycle_product_partner_list", {
    ...listView,
    Controller: CycleProductPartnerListController,
    buttonTemplate: "customer_itch_cycle.ListButtons",
});
