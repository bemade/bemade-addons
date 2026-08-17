/* Copyright 2026 Bemade Inc. — AGPL-3
 *
 * Envoi des approbations d'Hermes SANS recharger la page — par SURCHARGE OWL
 * du composant Message de Discuss (façon idiomatique Odoo 19), et non par un
 * écouteur global au niveau du document.
 *
 * POURQUOI CE DÉTOUR. Le corps d'un message Discuss est rendu par `t-out`
 * (@mail/core/common/message, <div t-ref="body">) : du HTML brut, pas des
 * composants OWL. On ne peut donc pas remplacer les <a> par des <button>
 * OWL sans réécrire tout le rendu du corps. On patche donc `Message` pour,
 * une fois le corps monté, câbler NOS boutons (marqués « o_hermes_approve »,
 * classe posée côté hermes-agent).
 *
 * CE QUE LA SURCHARGE APPORTE sur l'écouteur global :
 *   - portée au COMPOSANT (via la ref `body`), pas au document entier ;
 *   - services Odoo natifs : notification (retour visuel), rpc jamais requis
 *     ici car on parle au contrôleur en fetch ;
 *   - nettoyage automatique par useEffect quand le message se re-rend.
 *
 * ⚠️ COUPLAGE ASSUMÉ : ce patch dépend de la structure interne de Message
 * (ref "body"). Une montée de version d'Odoo peut le casser — d'où le REPLI :
 * les commandes textuelles restent affichées sous les boutons si ce patch ne
 * charge pas. La mise en forme ne retire jamais un moyen d'agir.
 */
import {Message} from "@mail/core/common/message";
import {getHermesApprovalUrl} from "./hermes_url";
import {patch} from "@web/core/utils/patch";
import {useEffect} from "@odoo/owl";
import {useService} from "@web/core/utils/hooks";

patch(Message.prototype, {
  setup() {
    super.setup();
    this.hermesNotif = useService("notification");
    // Se déclenche à chaque (re)rendu du corps du message. On y cherche
    // NOS boutons et on leur pose un gestionnaire de clic. useEffect rend
    // le nettoyage (retrait des écouteurs) automatique.
    useEffect(
      (bodyEl) => {
        if (!bodyEl) {
          return;
        }
        const boutons = bodyEl.querySelectorAll("a.o_hermes_approve");
        if (!boutons.length) {
          return;
        }
        const onClick = (ev) => {
          const lien = ev.currentTarget;
          const href = lien.getAttribute("href");
          if (!href) {
            return;
          }
          ev.preventDefault();
          const url = getHermesApprovalUrl(href, window.location.origin);
          if (!url) {
            return;
          }
          const body = new URLSearchParams({
            csrf_token: odoo.csrf_token,
          });
          const groupe = lien.closest(".o_hermes_approval");
          const figer = () => {
            if (groupe) {
              groupe.querySelectorAll("a.o_hermes_approve").forEach((b) => {
                b.style.pointerEvents = "none";
                b.style.opacity = "0.5";
              });
            }
          };
          fetch(url, {
            method: "POST",
            credentials: "same-origin",
            body,
            headers: {"X-Hermes-Ajax": "1"},
          })
            .then((rep) => {
              if (rep.ok || rep.status === 204) {
                figer();
                this.hermesNotif.add("Envoyé à Hermes.", {
                  type: "success",
                });
              } else {
                this.hermesNotif.add(
                  "Envoi impossible. Utilisez la commande textuelle.",
                  {type: "danger"}
                );
              }
            })
            .catch(() => {
              this.hermesNotif.add(
                "Envoi impossible. Utilisez la commande textuelle.",
                {type: "danger"}
              );
            });
        };
        boutons.forEach((b) => b.addEventListener("click", onClick));
        return () => boutons.forEach((b) => b.removeEventListener("click", onClick));
      },
      () => [this.messageBody?.el, this.message?.body]
    );
  },
});
