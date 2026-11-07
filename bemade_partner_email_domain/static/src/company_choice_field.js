import {
  BadgeSelectionField,
  badgeSelectionField,
} from "@web/views/fields/badge_selection/badge_selection_field";
import {registry} from "@web/core/registry";

/**
 * Candidate companies as clickable badges, usable directly on a list row:
 * a click chooses the company (and saves the row), a click on the chosen
 * badge clears the choice. Nothing is selected by default.
 */
export class CompanyChoiceField extends BadgeSelectionField {
  static template = "bemade_partner_email_domain.CompanyChoiceField";

  async onChoose(ev, value) {
    // Keep the list from opening/editing the row on this click.
    ev.target.special_click = true;
    if (this.value === value) {
      await this.props.record.update({[this.props.name]: false}, {save: true});
      return;
    }
    const option = this.options.find((o) => o[0] === value);
    await this.props.record.update(
      {[this.props.name]: {id: option[0], display_name: option[1]}},
      {save: true}
    );
  }
}

export const companyChoiceField = {
  ...badgeSelectionField,
  component: CompanyChoiceField,
  supportedTypes: ["many2one"],
  extractProps: (fieldInfo, dynamicInfo) => ({
    ...badgeSelectionField.extractProps(fieldInfo, dynamicInfo),
    // Editable on every row, not only on the row in edition.
    readonly: dynamicInfo.readonly,
  }),
};

registry.category("fields").add("email_domain_company_choice", companyChoiceField);
