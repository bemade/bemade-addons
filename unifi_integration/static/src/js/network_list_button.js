/** @odoo-module */
import { ListController } from "@web/views/list/list_controller";
import { registry } from '@web/core/registry';
import { listView } from '@web/views/list/list_view';

/**
 * Controller pour la vue liste des réseaux avec un bouton de synchronisation
 * Cette classe étend le contrôleur de liste standard pour ajouter un bouton de synchronisation
 * Le bouton est visible uniquement si tous les réseaux appartiennent au même site
 */
export class NetworkListController extends ListController {
    /**
     * @override
     */
    static components = {
        ...ListController.components,
    };
    
    /**
     * @override
     */
    static template = "unifi_integration.NetworkListView.Buttons";
    setup() {
        super.setup();
        this.orm = this.env.services.orm;
        this.notification = this.env.services.notification;
        this.buttonVisible = false;
        this.singleSiteId = null;
    }
    
    /**
     * Méthode appelée après le rendu du composant
     * Utilisée pour vérifier si tous les réseaux appartiennent au même site
     */
    mounted() {
        super.mounted();
        this.checkSingleSite();
    }
    
    /**
     * Méthode appelée lorsque les données du modèle sont mises à jour
     */
    async onWillStart() {
        await super.onWillStart();
        this.checkSingleSite();
    }
    
    /**
     * Méthode appelée lorsque les données du modèle sont mises à jour
     */
    async willUpdateProps() {
        await super.willUpdateProps();
        this.checkSingleSite();
    }
    
    /**
     * Vérifie si tous les réseaux affichés appartiennent au même site
     * Met à jour this.buttonVisible en conséquence
     */
    async checkSingleSite() {
        console.log('checkSingleSite appelé');
        console.log('this.model:', this.model);
        
        if (!this.model.root || !this.model.root.records || !this.model.root.records.length) {
            console.log('Aucun enregistrement trouvé');
            this.buttonVisible = false;
            this.singleSiteId = null;
            return;
        }
        
        console.log('Nombre d\'enregistrements:', this.model.root.records.length);
        
        // Récupérer tous les site_id uniques
        const siteIds = new Set();
        for (const record of this.model.root.records) {
            console.log('Record data:', record.data);
            if (record.data.site_id && record.data.site_id[0]) {
                siteIds.add(record.data.site_id[0]);
                console.log('Ajout du site_id:', record.data.site_id[0]);
            } else {
                console.log('Pas de site_id pour cet enregistrement');
            }
        }
        
        console.log('Nombre de sites uniques:', siteIds.size);
        console.log('Sites IDs:', Array.from(siteIds));
        
        // Le bouton est visible uniquement s'il y a exactement un site_id
        this.buttonVisible = siteIds.size === 1;
        this.singleSiteId = this.buttonVisible ? Array.from(siteIds)[0] : null;
        
        console.log('buttonVisible:', this.buttonVisible);
        console.log('singleSiteId:', this.singleSiteId);
        
        // Forcer la mise à jour du rendu
        this.render();
    }
    
    /**
     * Gestionnaire de clic pour le bouton de synchronisation des réseaux
     */
    async onSyncNetworksClick() {
        if (!this.buttonVisible) {
            this.notification.add("Impossible de synchroniser des réseaux de sites différents", {
                type: "warning",
            });
            return;
        }
        
        // Afficher une alerte pour tester
        alert("Ça marche - Synchronisation des réseaux du site " + this.singleSiteId);
        
        // Notification de succès
        this.notification.add("Ça marche - Synchronisation des réseaux du site " + this.singleSiteId, {
            type: "success",
        });
    }
}

// Enregistrement de la vue liste personnalisée
registry.category("views").add("unifi_network_list", {
    ...listView,
    Controller: NetworkListController,
    buttonTemplate: "unifi_integration.NetworkListView.Buttons",
});
