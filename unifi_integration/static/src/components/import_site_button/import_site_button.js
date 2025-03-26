/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { listView } from "@web/views/list/list_view";
import { ListController } from "@web/views/list/list_controller";

/**
 * Contrôleur personnalisé pour la vue liste des sites UniFi
 * Ajoute un bouton pour importer un site UniFi
 */
export class UnifiSiteListController extends ListController {
    setup() {
        super.setup();
        this.action = useService("action");
    }

    /**
     * Méthode appelée lorsque l'utilisateur clique sur le bouton d'importation
     * Lance l'assistant d'importation de site UniFi
     */
    onImportSiteClick() {
        this.action.doAction("unifi_integration.action_import_unifi_site");
    }
}

/**
 * Vue liste personnalisée pour les sites UniFi
 * Utilise le contrôleur personnalisé et le template de bouton
 */
export const UnifiSiteListView = {
    ...listView,
    Controller: UnifiSiteListController,
    buttonTemplate: "unifi_integration.ImportUnifiSiteButton",
};

// Enregistrement de la vue personnalisée dans le registre des vues
registry.category("views").add("unifi_site_list", UnifiSiteListView);
