// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "see-encryption",
    title: "Voir le choix de chiffrement SMTP",
    narration:
      "Dans la fiche de votre boîte courriel, le champ Chiffrement SMTP offre trois choix : Aucun, STARTTLS et SSL/TLS.",
    selector: ".o_form_view .o_field_widget[name='smtp_encryption']",
    action: "assert",
  },
  {
    id: "open-choices",
    title: "Ouvrir la liste des choix",
    narration: "Ouvrons la liste des choix de chiffrement.",
    selector:
      ".o_form_view .o_field_widget[name='smtp_encryption'] .o_select_menu_toggler",
    action: "click",
  },
  {
    id: "choose-ssl",
    title: "Choisir SSL/TLS",
    narration: "Si votre serveur utilise le port 465, choisissez SSL/TLS.",
    selector: ".o_select_menu_menu .o_select_menu_item",
    containsText: "SSL/TLS",
    action: "click",
  },
  {
    id: "set-port",
    title: "Saisir le port 465",
    narration: "Indiquez ensuite le port 465 du serveur d'envoi.",
    selector: ".o_form_view .o_field_widget[name='smtp_port'] input",
    action: "fill",
    value: "465",
  },
  {
    id: "save",
    title: "Enregistrer",
    narration:
      "Enregistrez. Les réponses envoyées depuis cette boîte utiliseront désormais une connexion SSL/TLS.",
    selector: ".o_form_button_save",
    action: "click",
  },
  {
    id: "saved",
    title: "Vérifier l'enregistrement",
    narration:
      "Le formulaire n'indique plus de modification en attente : le réglage est enregistré.",
    selector:
      ".o_form_view:not(:has(.o_form_status_indicator_buttons:not(.invisible)))",
    action: "assert",
  },
];
