// Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
// Pure data, no imports: shared by the web_tour and the demo video.
export default [
  {
    id: "both-unread",
    title: "Repérer deux conversations non lues",
    narration: "Deux conversations sont en gras : vous ne les avez pas encore lues.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Omega']).fw-bold",
    action: "assert",
  },
  {
    id: "open-omega",
    title: "Ouvrir la première conversation",
    narration: "Ouvrons la première conversation.",
    selector:
      ".o_list_renderer tr.o_data_row:has(td[name='name'][data-tooltip^='Omega']) td[name='name']",
    action: "click",
  },
  {
    id: "form-opens",
    title: "Voir la conversation et son fil",
    narration: "La conversation s'ouvre avec son fil de discussion.",
    selector: ".o_form_view .o-mail-Chatter",
    action: "assert",
  },
  {
    id: "next-record",
    title: "Passer à la conversation suivante",
    narration:
      "Avec la flèche suivante de la fiche, nous passons à la conversation suivante sans retourner à la liste.",
    selector: ".o_pager_next",
    action: "click",
  },
  {
    id: "second-record",
    title: "Voir la deuxième conversation",
    narration: "La deuxième conversation est ouverte.",
    selector: ".o_pager_value",
    containsText: "2",
    action: "assert",
  },
  {
    id: "back-to-list",
    title: "Revenir à la liste",
    narration: "Retournons à la liste des conversations.",
    selector: ".o_control_panel .breadcrumb-item:not(.active) a",
    action: "click",
  },
  {
    id: "now-read",
    title: "Vérifier que les conversations sont lues",
    narration:
      "Les deux conversations ne sont plus en gras : elles sont lues pour vous, peu importe comment vous les avez ouvertes. Vos collègues les voient toujours comme non lues.",
    selector:
      ".o_list_renderer:not(:has(tr.o_data_row.fw-bold)) tr.o_data_row:has(td[name='name'][data-tooltip^='Psi'])",
    action: "assert",
  },
];
