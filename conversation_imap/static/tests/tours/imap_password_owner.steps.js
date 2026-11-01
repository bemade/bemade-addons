// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "open-account",
    title: "Ouvrir votre compte de messagerie personnel",
    narration:
      "Voici votre compte de messagerie personnel. Vous voyez ses paramètres, mais jamais un mot de passe déjà enregistré.",
    selector: ".o_form_view .o_field_widget[name='password_set']",
    action: "assert",
  },
  {
    id: "type-password",
    title: "Saisir le nouveau mot de passe",
    narration:
      "Saisissez le nouveau mot de passe de votre compte dans le champ prévu à cet effet.",
    selector: ".o_form_view .o_field_widget[name='new_password'] input",
    action: "fill",
    value: "tour-secret",
  },
  {
    id: "save",
    title: "Enregistrer",
    narration:
      "Enregistrez. La synchronisation de votre compte utilisera désormais ce mot de passe.",
    selector: ".o_form_button_save",
    action: "click",
  },
  {
    id: "saved",
    title: "Vérifier l'enregistrement",
    narration:
      "Le formulaire n'indique plus de modification en attente : le mot de passe est enregistré, sans jamais être affiché.",
    selector:
      ".o_form_view:not(:has(.o_form_status_indicator_buttons:not(.invisible)))",
    action: "assert",
  },
];
