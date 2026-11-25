/** @odoo-module **/

import {RelationalModel} from '@web/model/relational_model/relational_model';
import {patch} from '@web/core/utils/patch';
import {makeActiveField} from "@web/model/relational_model/utils";
import {getParentField, loadChildRecords} from "./recursive_utils";

patch(RelationalModel.prototype, {
    // TODO: Modify the domain to include only records with parentField = False in the root search

    setup(params, services) {
        super.setup(...arguments);
        this.hooks.onRootLoaded = () => {
            const root = this.root;
            const config = this.root.config;
            if (config.recursive && root.records) {
                this._loadChildren(root.records, config).then(() => {
                    return root;
                });
            }
        }
    },
    async _loadData(config) {
        if (config.recursive) {
            const parentField = await this._get_parent_field(config.resModel);
            const domain = [parentField, '=', false];
            if (!(domain in config.domain)) {
                config.domain = config.domain.concat([domain]);
            }
            if (!(parentField in config.activeFields) || !config.activeFields[parentField]) {
                config.activeFields[parentField] = makeActiveField()
            }
        }
        return super._loadData(config);
    },
    async _loadChildren(records, config = undefined) {
        if (!records) {
            return [];
        }
        if (!config) {
            config = this.config;
        }
        if (!Array.isArray(records)) {
            records = [records];
        }
        await loadChildRecords({
            orm: this.orm,
            model: this,
            config,
            records,
            maxDepth: (this.config && this.config.recursiveDepth) || config.recursiveDepth,
        });
    },
    async _get_parent_field(model) {
        return getParentField(this.orm, model);
    },

    findRecordInHierarchy(resId) {
        const records = this.root.records;
        const target = String(resId);

        function findRecord(list) {
            for (let record of list) {
                if (String(record.resId) === target) {
                    return record;
                }
                if (record.children && record.children.length > 0) {
                    const found = findRecord(record.children);
                    if (found) {
                        return found;
                    }
                }
            }
        }

        return findRecord(records) || null;
    }
});
