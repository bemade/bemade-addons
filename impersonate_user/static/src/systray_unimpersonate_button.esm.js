/** @odoo-module **/

import {Component} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";
import {session} from "@web/session";
import {registry} from "@web/core/registry";

export class SystrayUnimpersonateButton extends Component {
  setup() {
    this.rpc = useService("rpc");
    this.action = useService("action");
  }

  async unimpersonate() {
    this.rpc("/unimpersonate", {}).then((result) => this.action.doAction(result));
  }

  get isVisible() {
    return session.user_impersonated;
  }
}

SystrayUnimpersonateButton.props = {};
SystrayUnimpersonateButton.template = "impersonate_user.SystrayUnimpersonateButton";
registry.category("systray").add("unimpersonate_button", {
  Component: SystrayUnimpersonateButton,
});
