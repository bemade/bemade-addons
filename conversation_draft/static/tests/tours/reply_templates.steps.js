// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "new-conversation",
    title: "Créer une conversation",
    narration: "Commençons par ouvrir une nouvelle conversation.",
    selector: ".o_list_button_add",
    action: "click",
  },
  {
    id: "conversation-name",
    title: "Nommer la conversation",
    narration: "Donnons-lui un nom.",
    selector: ".o_field_widget[name='name'] input",
    action: "fill",
    value: "Question de livraison",
  },
  {
    id: "conversation-save",
    title: "Enregistrer la conversation",
    narration: "Puis enregistrons-la.",
    selector: ".o_form_button_save",
    action: "click",
  },
  {
    id: "no-template-button",
    title: "Constater l'absence du bouton de modèle",
    narration:
      "Tant qu'aucun modèle de réponse n'existe, seul le bouton Répondre est proposé. Le bouton de réponse avec modèle est masqué.",
    selector:
      ".o_form_statusbar:has(button[name='action_open_draft']):not(:has(button[name='action_open_draft_with_template']))",
    action: "assert",
  },
  {
    id: "open-templates",
    title: "Ouvrir les modèles de réponse",
    narration: "L'administrateur ouvre le menu Modèles de réponse, sous Conversations.",
    selector:
      ".o_menu_sections [data-menu-xmlid='conversation_draft.menu_mail_reply_template']",
    action: "click",
  },
  {
    id: "new-template",
    title: "Créer un modèle",
    narration: "Il crée un nouveau modèle.",
    selector: ".o_list_button_add",
    action: "click",
  },
  {
    id: "template-name",
    title: "Nommer le modèle",
    narration: "Il lui donne un nom.",
    selector: ".o_field_widget[name='name'] input",
    action: "fill",
    value: "Accusé de réception",
  },
  {
    id: "template-save",
    title: "Enregistrer le modèle",
    narration:
      "Puis il l'enregistre. Le modèle est automatiquement destiné aux conversations.",
    selector: ".o_form_button_save",
    action: "click",
  },
  {
    id: "back-to-conversations",
    title: "Retourner aux conversations",
    narration: "Retournons dans la liste des conversations.",
    selector:
      ".o_menu_sections [data-menu-xmlid='conversation_base.menu_mail_conversation']",
    action: "click",
  },
  {
    id: "open-conversation",
    title: "Ouvrir la conversation",
    narration: "Ouvrons la conversation créée plus tôt.",
    selector: ".o_data_row:contains('Question de livraison') td[name='name']",
    action: "click",
  },
  {
    id: "template-button",
    title: "Voir le bouton de réponse avec modèle",
    narration:
      "Le bouton de réponse avec modèle apparaît maintenant, sans mise à jour ni redémarrage.",
    selector: ".o_form_statusbar button[name='action_open_draft_with_template']",
    action: "assert",
  },
];
