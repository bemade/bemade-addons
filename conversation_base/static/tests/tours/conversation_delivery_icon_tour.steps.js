// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
//
// The conversation holds a reply that was delivered; its internal members
// were notified in the app. The message must carry no envelope icon that
// reads as a failed delivery.
export default [
  {
    id: "open-conversation",
    title: "Ouvrir la conversation",
    narration: "Ouvrons la conversation à laquelle nous avons répondu.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Livraison']) td[name='name']",
    action: "click",
  },
  {
    id: "reply-shown",
    title: "Voir la réponse envoyée",
    narration: "Notre réponse figure dans le fil de la conversation.",
    selector: ".o-mail-Message",
    containsText: "Votre commande part demain",
    action: "assert",
  },
  {
    id: "no-failure-icon",
    title: "Vérifier l'absence d'icône d'échec",
    narration:
      "Le message n'affiche aucune icône d'échec d'envoi : il a bien été livré.",
    selector: ".o-mail-Message:not(:has(.o-mail-Message-notification))",
    containsText: "Votre commande part demain",
    action: "assert",
  },
];
