/** @odoo-module **/

import {RelationalModel} from '@web/model/relational_model/relational_model';
import {patch} from '@web/core/utils/patch';
import {getFieldsSpec, getBasicEvalContext, makeActiveField} from "@web/model/relational_model/utils";

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
        const {resModel, activeFields, fields, context} = config;
        if (!resModel) {
            return [];
        }
        const parentField = await this._get_parent_field(resModel);
        if (!parentField) {
            return [];
        }
        const evalContext = getBasicEvalContext(config);
        const fieldSpec = getFieldsSpec(activeFields, fields, evalContext);
        // Fetch records with the additional field
        const parentIds = records.map(record => record.resId);

        const children = await this.orm.webSearchRead(
            resModel, [[parentField, "in", parentIds]], {
                context: {...context},
                specification: fieldSpec,
            });

        if (children && children.length) {
            // Track children by grouping child records under each parent
            const childrenByParent = {};
            for (const child of children.records) {
                const parentId = child[parentField].id;
                if (parentId) {
                    if (!childrenByParent[parentId]) {
                        childrenByParent[parentId] = [];
                    }
                    childrenByParent[parentId].push(child);
                }
            }

            for (const parent of records) {
                if (parent.depth == undefined) {
                    parent.depth = 0;
                }
                if (parent.expanded == undefined) {
                    parent.expanded = false;
                }
                if (!parent.childrenFetched) {
                    if (childrenByParent[parent.resId]) {
                        const childRecords = childrenByParent[parent.resId];
                        parent.children = []
                        for (const child of childRecords) {
                            const childRecord = new this.constructor.Record(
                                this,
                                {
                                    context: context,
                                    activeFields: activeFields,
                                    resModel: resModel,
                                    fields: fields,
                                    resId: child.id,
                                    resIds: [child.id],
                                    isMonoRecord: true,
                                    currentCompanyId: parent.currentCompanyId,
                                    mode: parent.mode,
                                },
                                child,
                                {manuallyAdded: false},
                            );
                            parent.children.push(childRecord);
                            childRecord.parent = parent;
                            childRecord.depth = parent.depth + 1;
                            childRecord.expanded = false;
                            childRecord.childrenFetched = false;
                        }
                    }
                    parent.childrenFetched = true;
                }
            }
        }
    },
    async _get_parent_field(model) {
        return await this.orm.call(
            'parent.field.service',
            'get_parent_field',
            [model],
        );
    },

    findRecordInHierarchy(resId) {
        const records = this.root.records;

        function findRecord(records) {
            for (let record of records) {
                if (record.resId === resId) {
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
