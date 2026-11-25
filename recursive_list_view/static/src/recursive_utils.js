/** @odoo-module **/

import { getBasicEvalContext, getFieldsSpec } from "@web/model/relational_model/utils";

const parentFieldPromises = new Map();

/**
 * Name of the parent field of `resModel` (its `_parent_name`, else `parent_id`),
 * fetched once per model and cached for the session.
 */
export function getParentField(orm, resModel) {
    if (!parentFieldPromises.has(resModel)) {
        const promise = orm.call("parent.field.service", "get_parent_field", [resModel]);
        promise.catch(() => parentFieldPromises.delete(resModel));
        parentFieldPromises.set(resModel, promise);
    }
    return parentFieldPromises.get(resModel);
}

/**
 * Whether rows below `record` may be shown, given `maxDepth` (the number of
 * levels the list may show, its own rows being level 1; 0/undefined = no cap).
 */
export function canShowChildren(record, maxDepth) {
    return !maxDepth || (record.depth || 0) + 1 < maxDepth;
}

/**
 * Fetch, in one request, the children of every record of `records` that has not
 * fetched them yet, and attach them as `record.children` (only when there are
 * some, so the expand button shows only on records with children).
 *
 * @param {Object} params
 * @param {Object} params.orm the orm service
 * @param {Object} params.model the RelationalModel the records belong to
 * @param {Object} params.config config of the list (resModel, activeFields, fields, context)
 * @param {Object[]} params.records the records whose children to fetch
 * @param {number} [params.maxDepth] depth cap, see canShowChildren
 * @param {Object} [params.recordOptions] extra options for the child Record datapoints
 */
export async function loadChildRecords({ orm, model, config, records, maxDepth, recordOptions }) {
    const todo = [];
    for (const record of records || []) {
        if (record.depth === undefined) {
            record.depth = 0;
        }
        if (record.expanded === undefined) {
            record.expanded = false;
        }
        if (record.childrenFetched || record.childrenLoading || !record.resId) {
            continue;
        }
        if (!canShowChildren(record, maxDepth)) {
            record.childrenFetched = true;
            continue;
        }
        todo.push(record);
    }
    const { resModel, activeFields, fields, context } = config;
    if (!todo.length || !resModel) {
        return;
    }
    for (const record of todo) {
        record.childrenLoading = true;
    }
    try {
        const parentField = await getParentField(orm, resModel);
        if (!parentField) {
            return;
        }
        const specification = getFieldsSpec(activeFields, fields, getBasicEvalContext(config));
        const parentFieldActive = parentField in activeFields;
        if (!(parentField in specification)) {
            specification[parentField] = {};
        }
        const { records: rows } = await orm.webSearchRead(
            resModel,
            [[parentField, "in", todo.map((record) => record.resId)]],
            { context: { ...context }, specification }
        );
        const rowsByParent = {};
        for (const row of rows) {
            const value = row[parentField];
            const parentId = value && typeof value === "object" ? value.id : value;
            if (!parentFieldActive) {
                delete row[parentField];
            }
            if (parentId) {
                (rowsByParent[parentId] ||= []).push(row);
            }
        }
        const RecordClass = model.constructor.Record;
        for (const record of todo) {
            const childRows = rowsByParent[record.resId];
            if (childRows) {
                record.children = childRows.map((row) => {
                    const child = new RecordClass(
                        model,
                        {
                            context,
                            activeFields,
                            resModel,
                            fields,
                            relationField: config.relationField,
                            resId: row.id,
                            resIds: [row.id],
                            isMonoRecord: true,
                            currentCompanyId: config.currentCompanyId,
                            mode: "readonly",
                        },
                        row,
                        { manuallyAdded: false, ...(recordOptions || {}) }
                    );
                    child.parent = record;
                    child.depth = (record.depth || 0) + 1;
                    child.expanded = false;
                    child.childrenFetched = false;
                    return child;
                });
            }
            record.childrenFetched = true;
        }
    } finally {
        for (const record of todo) {
            record.childrenLoading = false;
        }
    }
}
