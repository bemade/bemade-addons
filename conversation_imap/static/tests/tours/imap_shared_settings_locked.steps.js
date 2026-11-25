// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "open-shared-account",
    title: "Ouvrir un compte de messagerie partagé",
    narration:
      "Voici un compte de messagerie partagé, qui n'appartient à personne en particulier.",
    selector: ".o_form_view .o_field_widget[name='imap_host'] input",
    action: "assert",
  },
  {
    id: "change-server",
    title: "Modifier le serveur IMAP",
    narration: "Essayons de remplacer le serveur de courrier entrant.",
    selector: ".o_form_view .o_field_widget[name='imap_host'] input",
    action: "fill",
    value: "autre.example.com",
  },
  {
    id: "save",
    title: "Enregistrer",
    narration: "Enregistrons la modification.",
    selector: ".o_form_button_save",
    action: "click",
  },
  {
    id: "refused",
    title: "Lire le message de refus",
    narration:
      "Le changement est refusé : seul un gestionnaire des conversations ou un administrateur peut modifier les paramètres du serveur d'un compte partagé.",
    selector: ".modal .modal-body",
    containsText: "Only a Conversations manager",
    action: "assert",
  },
  {
    id: "close",
    title: "Fermer le message",
    narration: "On referme le message.",
    selector: ".modal .modal-footer .btn-primary",
    action: "click",
  },
  {
    id: "discard",
    title: "Annuler la modification",
    narration:
      "On annule la modification : le serveur du compte est resté tel qu'il était.",
    selector: ".o_form_button_cancel",
    action: "click",
  },
  {
    id: "clean",
    title: "Vérifier que rien n'a changé",
    narration: "Le formulaire n'a plus aucune modification en attente.",
    selector:
      ".o_form_view:not(:has(.o_form_status_indicator_buttons:not(.invisible)))",
    action: "assert",
  },
];
