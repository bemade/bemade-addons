odoo.define('odoo_unifi_manager.firewall_rule_wizard', function (require) {
    "use strict";

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var viewRegistry = require('web.view_registry');

    var FirewallRuleWizardController = FormController.extend({
        _onFieldChanged: function (event) {
            var self = this;
            var fieldName = event.name;
            
            if (fieldName === 'template_id') {
                var templateId = event.data.changes.template_id.id;
                if (templateId) {
                    // Récupérer les données du template
                    this._rpc({
                        model: 'unifi.firewall.rule.template',
                        method: 'read',
                        args: [[templateId], ['action', 'src_ip', 'dst_ip', 'protocol', 'port']]
                    }).then(function (result) {
                        if (result && result.length > 0) {
                            var template = result[0];
                            // Mettre à jour les champs seulement si ils ont des valeurs
                            var changes = {};
                            if (template.action) changes.action = template.action;
                            if (template.src_ip) changes.src_ip = template.src_ip;
                            if (template.dst_ip) changes.dst_ip = template.dst_ip;
                            if (template.protocol) changes.protocol = template.protocol;
                            if (template.port) changes.port = template.port;

                            // Appliquer les changements au modèle
                            self.model.setData(changes);
                        }
                    });
                }
            }
            return this._super.apply(this, arguments);
        },
    });

    var FirewallRuleWizardFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: FirewallRuleWizardController,
        }),
    });

    viewRegistry.add('firewall_rule_wizard_form', FirewallRuleWizardFormView);

    return {
        FirewallRuleWizardController: FirewallRuleWizardController,
        FirewallRuleWizardFormView: FirewallRuleWizardFormView,
    };
});
