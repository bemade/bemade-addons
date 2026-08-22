/**
 * Task 1414: the portal patient combo — a typeahead over a real <select>.
 *
 * The server renders a plain <select name="…"> (the posted value, the no-JS
 * fallback) inside .o_sc_patient_combo (views/portal_widgets_templates.xml,
 * template portal_patient_combo). This script hides that select and shows a
 * text input + a filtered list built from the SAME <option>s — nothing is
 * fetched: the combo can only ever offer what the page already renders.
 *
 * Behaviour:
 *  - typing filters the options (every word typed must start a word of the
 *    option's « last first » key, accents / case ignored — « zo ab » and
 *    « ab zo » both find « Äbel, Zoé »); <optgroup> headings are kept, a
 *    group disappears when none of its options match;
 *  - ArrowDown / ArrowUp move, Enter picks (and never submits the form while
 *    the list is open), Escape closes and restores the current selection,
 *    Tab closes; rows are tall enough for a finger;
 *  - picking writes the id back to the hidden select and fires `change`;
 *    the input shows the selection's label;
 *  - « × » clears when the select allows an empty value (data-combo-clearable,
 *    i.e. the template was given combo_empty_label);
 *  - a required select with nothing picked blocks the submit and opens the
 *    list instead of the browser's unfocusable-control error.
 *
 * Progressive enhancement, vanilla, in the style of the addon's other portal
 * scripts. Strings come from the template's data- attributes (translated
 * server-side). Combos injected later (a #1412-style dialog fragment) are
 * enhanced on Bootstrap's shown.bs.modal, or by window.scPatientCombo.enhance(root).
 */
(function () {
    "use strict";

    var BLUR_CLOSE_MS = 150;

    function normalize(text) {
        var s = (text || "").toString();
        if (s.normalize) {
            s = s.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        }
        return s.toLowerCase().replace(/\s+/g, " ").trim();
    }

    function matches(key, words, query) {
        if (!query) {
            return true;
        }
        if (key.indexOf(query) !== -1) {
            return true;
        }
        var tokens = query.split(" ");
        for (var i = 0; i < tokens.length; i++) {
            var found = false;
            for (var j = 0; j < words.length; j++) {
                if (words[j].indexOf(tokens[i]) === 0) {
                    found = true;
                    break;
                }
            }
            if (!found) {
                return false;
            }
        }
        return true;
    }

    function readOptions(select) {
        // [{group, option, key, words, label}] in DOM order, empty option skipped.
        var items = [];
        var groupIndex = 0;
        Array.prototype.forEach.call(select.children, function (child) {
            if (child.tagName === "OPTGROUP") {
                groupIndex += 1;
                var groupLabel = child.getAttribute("label") || "";
                Array.prototype.forEach.call(child.children, function (opt) {
                    pushOption(items, opt, groupIndex, groupLabel);
                });
            } else if (child.tagName === "OPTION") {
                pushOption(items, child, 0, "");
            }
        });
        return items;
    }

    function pushOption(items, opt, groupIndex, groupLabel) {
        if (!opt.value) {
            return;
        }
        var label = opt.textContent.trim();
        var key = normalize(opt.getAttribute("data-key") || label.replace(",", " "));
        items.push({
            option: opt,
            groupIndex: groupIndex,
            groupLabel: groupLabel,
            label: label,
            key: key,
            words: key ? key.split(" ") : [],
        });
    }

    function selectedLabel(select) {
        var opt = select.options[select.selectedIndex];
        return opt && opt.value ? opt.textContent.trim() : "";
    }

    function enhance(wrapper) {
        var select = wrapper.querySelector("select");
        if (!select || select.getAttribute("data-combo-bound")) {
            return;
        }
        select.setAttribute("data-combo-bound", "1");

        var small = select.classList.contains("form-select-sm");
        var clearable = !!select.getAttribute("data-combo-clearable");
        var placeholder = wrapper.getAttribute("data-placeholder") || "";
        var emptyLabel = wrapper.getAttribute("data-empty-label") || "";
        var clearTitle = wrapper.getAttribute("data-clear-title") || "";
        var listId = (select.id || select.name || "combo") + "_combo_list_" +
            Math.random().toString(36).slice(2, 8);

        var items = readOptions(select);

        // --- build the UI -------------------------------------------------
        var group = document.createElement("div");
        group.className = "input-group o_sc_combo_input_group" + (small ? " input-group-sm" : "");

        var input = document.createElement("input");
        input.type = "text";
        input.className = "form-control o_sc_combo_input" + (small ? " form-control-sm" : "");
        input.setAttribute("autocomplete", "off");
        input.setAttribute("autocapitalize", "off");
        input.setAttribute("spellcheck", "false");
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-autocomplete", "list");
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("aria-controls", listId);
        if (placeholder) {
            input.placeholder = placeholder;
        }
        if (select.id) {
            // The page's <label for=select-id> must keep pointing at something
            // focusable: move the id to the input, the select keeps its name.
            input.id = select.id;
            select.removeAttribute("id");
        }
        input.value = selectedLabel(select);
        group.appendChild(input);

        var clearButton = null;
        if (clearable) {
            clearButton = document.createElement("button");
            clearButton.type = "button";
            clearButton.className = "btn btn-outline-secondary o_sc_combo_clear";
            clearButton.setAttribute("title", clearTitle);
            clearButton.setAttribute("aria-label", clearTitle);
            clearButton.innerHTML = "&times;";
            group.appendChild(clearButton);
        }

        var list = document.createElement("ul");
        list.className = "list-group o_sc_combo_list d-none";
        list.id = listId;
        list.setAttribute("role", "listbox");

        select.classList.add("d-none");
        select.setAttribute("tabindex", "-1");
        select.setAttribute("aria-hidden", "true");
        wrapper.appendChild(group);
        wrapper.appendChild(list);
        wrapper.classList.add("o_sc_patient_combo_enhanced");

        // --- state ----------------------------------------------------------
        var open = false;
        var visible = [];     // items currently rendered, in order
        var active = -1;      // index into `visible`
        var blurTimer = null;

        function updateClear() {
            if (clearButton) {
                clearButton.classList.toggle("d-none", !select.value);
            }
        }

        function setExpanded(flag) {
            open = flag;
            list.classList.toggle("d-none", !flag);
            // The stylesheet lifts the clipping of an enclosing .card
            // (overflow: hidden in the website theme) while the list is open.
            wrapper.classList.toggle("o_sc_combo_open", flag);
            input.setAttribute("aria-expanded", flag ? "true" : "false");
            if (!flag) {
                active = -1;
                input.removeAttribute("aria-activedescendant");
            }
        }

        function render(query) {
            var q = normalize(query);
            list.innerHTML = "";
            visible = [];
            var lastGroup = -1;
            items.forEach(function (item) {
                if (!matches(item.key, item.words, q)) {
                    return;
                }
                if (item.groupIndex && item.groupIndex !== lastGroup) {
                    var header = document.createElement("li");
                    header.className = "list-group-item o_sc_combo_group small text-muted fw-bold";
                    header.setAttribute("role", "presentation");
                    header.textContent = item.groupLabel;
                    list.appendChild(header);
                }
                lastGroup = item.groupIndex;
                var row = document.createElement("li");
                row.className = "list-group-item list-group-item-action o_sc_combo_item";
                row.setAttribute("role", "option");
                row.id = listId + "_" + visible.length;
                row.setAttribute("data-index", String(visible.length));
                row.setAttribute("aria-selected", item.option.value === select.value ? "true" : "false");
                row.textContent = item.label;
                if (item.option.value === select.value) {
                    row.classList.add("o_sc_combo_current");
                }
                list.appendChild(row);
                visible.push(item);
            });
            if (!visible.length) {
                var none = document.createElement("li");
                none.className = "list-group-item text-muted o_sc_combo_empty";
                none.setAttribute("role", "presentation");
                none.textContent = emptyLabel;
                list.appendChild(none);
            }
            // A filter in progress: the first match is ready for Enter.
            setActive(q && visible.length ? 0 : -1);
        }

        function setActive(index) {
            active = index;
            var rows = list.querySelectorAll(".o_sc_combo_item");
            Array.prototype.forEach.call(rows, function (row, i) {
                row.classList.toggle("active", i === index);
            });
            if (index >= 0 && rows[index]) {
                input.setAttribute("aria-activedescendant", rows[index].id);
                if (rows[index].scrollIntoView) {
                    rows[index].scrollIntoView({ block: "nearest" });
                }
            } else {
                input.removeAttribute("aria-activedescendant");
            }
        }

        function openList(query) {
            render(query);
            setExpanded(true);
        }

        function closeList(restore) {
            setExpanded(false);
            if (restore) {
                input.value = selectedLabel(select);
            }
        }

        function pick(item) {
            select.value = item.option.value;
            input.value = item.label;
            input.classList.remove("is-invalid");
            updateClear();
            closeList(false);
            select.dispatchEvent(new Event("change", { bubbles: true }));
        }

        function clear() {
            select.value = "";
            input.value = "";
            updateClear();
            select.dispatchEvent(new Event("change", { bubbles: true }));
            input.focus();
            openList("");
        }

        // --- events ---------------------------------------------------------
        input.addEventListener("focus", function () {
            if (blurTimer) {
                window.clearTimeout(blurTimer);
                blurTimer = null;
            }
            // Select-all so the next keystroke starts a fresh filter.
            if (input.value) {
                input.select();
            }
            openList("");
        });
        input.addEventListener("input", function () {
            openList(input.value);
        });
        input.addEventListener("blur", function () {
            blurTimer = window.setTimeout(function () {
                closeList(true);
            }, BLUR_CLOSE_MS);
        });
        input.addEventListener("keydown", function (event) {
            switch (event.key) {
                case "ArrowDown":
                    event.preventDefault();
                    if (!open) {
                        openList(input.value);
                    }
                    if (visible.length) {
                        setActive(active < visible.length - 1 ? active + 1 : 0);
                    }
                    break;
                case "ArrowUp":
                    event.preventDefault();
                    if (!open) {
                        openList(input.value);
                    }
                    if (visible.length) {
                        setActive(active > 0 ? active - 1 : visible.length - 1);
                    }
                    break;
                case "Enter":
                    if (open) {
                        event.preventDefault();
                        if (active >= 0 && visible[active]) {
                            pick(visible[active]);
                        } else if (visible.length === 1) {
                            pick(visible[0]);
                        }
                    }
                    break;
                case "Escape":
                    if (open) {
                        event.preventDefault();
                        event.stopPropagation();
                        closeList(true);
                    }
                    break;
                case "Tab":
                    closeList(true);
                    break;
                default:
                    break;
            }
        });
        // mousedown/touchstart before the input blurs: keep focus, then pick
        // on click (the synthetic click after a tap included).
        list.addEventListener("mousedown", function (event) {
            event.preventDefault();
        });
        list.addEventListener("click", function (event) {
            var row = event.target.closest(".o_sc_combo_item");
            if (!row) {
                return;
            }
            var item = visible[parseInt(row.getAttribute("data-index"), 10)];
            if (item) {
                pick(item);
                input.focus();
                closeList(false);
            }
        });
        if (clearButton) {
            clearButton.addEventListener("mousedown", function (event) {
                event.preventDefault();
            });
            clearButton.addEventListener("click", clear);
        }
        // Something else changed the select (another script, a form reset):
        // mirror it.
        select.addEventListener("change", function () {
            if (!open) {
                input.value = selectedLabel(select);
            }
            updateClear();
        });
        var form = select.form;
        if (form) {
            form.addEventListener("reset", function () {
                window.setTimeout(function () {
                    input.value = selectedLabel(select);
                    updateClear();
                }, 0);
            });
            form.addEventListener("submit", function (event) {
                if (select.required && !select.value) {
                    event.preventDefault();
                    input.classList.add("is-invalid");
                    input.focus();
                }
            });
        }
        updateClear();
    }

    function enhanceAll(root) {
        var scope = root && root.querySelectorAll ? root : document;
        var wrappers = scope.querySelectorAll(".o_sc_patient_combo");
        Array.prototype.forEach.call(wrappers, enhance);
    }

    function init() {
        enhanceAll(document);
        if (!document.body.getAttribute("data-patient-combo-bound")) {
            document.body.setAttribute("data-patient-combo-bound", "1");
            // A dialog fragment injected later (#1412 style) may carry a combo.
            document.body.addEventListener("shown.bs.modal", function (event) {
                enhanceAll(event.target);
            });
        }
    }

    window.scPatientCombo = { enhance: enhanceAll };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init);
    } else {
        init();
    }
})();
