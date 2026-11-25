// A team member opens a mail account form: write-back and the owner are
// locked on the shared account (only a Conversations manager can change them) but editable
// on their own personal account.
export default [
  {
    id: "open_accounts",
    title: "Ouvrir la liste des comptes courriel",
    narration: "Vous ouvrez la liste des comptes courriel.",
    selector: ".o_list_view",
    action: "assert",
  },
  {
    id: "remove_mine_filter",
    title: "Afficher aussi les comptes partagés",
    narration:
      "Vous retirez le filtre sur vos comptes pour voir aussi les comptes partagés.",
    selector: ".o_searchview_facet .o_facet_remove",
    action: "click",
  },
  {
    id: "open_shared",
    title: "Ouvrir le compte partagé",
    narration: "Vous ouvrez le compte courriel partagé du soutien.",
    selector: ".o_data_row td[name='name']",
    action: "click",
    containsText: "Boîte courriel du soutien",
  },
  {
    id: "shared_locked",
    title: "L'écriture dans la boîte est verrouillée",
    narration:
      "L'option d'écriture dans la vraie boîte est verrouillée : seul un gestionnaire Conversations peut l'activer sur un compte partagé.",
    selector:
      ".o_form_view .o_field_widget[name='mailbox_writable'].o_readonly_modifier",
    action: "assert",
  },
  {
    id: "back_to_list",
    title: "Revenir à la liste des comptes",
    narration: "Vous revenez à la liste des comptes.",
    selector:
      ".o_breadcrumb .o_back_button, .o_breadcrumb .breadcrumb-item.o_back_button",
    action: "click",
  },
  {
    id: "open_personal",
    title: "Ouvrir votre compte personnel",
    narration: "Vous ouvrez votre propre compte courriel.",
    selector: ".o_data_row td[name='name']",
    action: "click",
    containsText: "Ma boîte courriel",
  },
  {
    id: "personal_editable",
    title: "L'option est modifiable sur votre compte personnel",
    narration:
      "Sur votre compte personnel, c'est vous qui décidez : l'option reste modifiable.",
    selector:
      ".o_form_view .o_field_widget[name='mailbox_writable']:not(.o_readonly_modifier)",
    action: "assert",
  },
  {
    id: "owner_locked",
    title: "Le propriétaire du compte est verrouillé",
    narration:
      "Le propriétaire reste verrouillé : seul un gestionnaire Conversations peut attribuer ou retirer le propriétaire d'un compte partagé ou dont l'écriture est activée, sans quoi un membre pourrait s'emparer d'un compte partagé et supprimer des courriels.",
    selector: ".o_form_view .o_field_widget[name='user_id'].o_readonly_modifier",
    action: "assert",
  },
];
