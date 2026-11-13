import {registry} from "@web/core/registry";

const CARD = ".o-mail-Message .o-mail-AttachmentContainer";

registry.category("web_tour.tours").add("bemade_attachment_heic_convert_tour", {
  steps: () => [
    {
      // The card buttons only show on hover (opacity 0), and whether headless Chrome counts
      // them as visible differs between environments, so click the button from its card.
      content: "The HEIC card offers Convert to JPEG",
      trigger: `${CARD}[title='IMG_TOUR.heic']:has(.o-bemade-ConvertHeic)`,
      run() {
        this.anchor.querySelector(".o-bemade-ConvertHeic").click();
      },
    },
    {
      content: "The card now previews the JPEG",
      trigger: `${CARD}[title='IMG_TOUR.jpg'] img.o-mail-AttachmentImage`,
    },
    {
      content: "The corrupt HEIC card offers Convert to JPEG",
      trigger: `${CARD}[title='BROKEN_TOUR.heic']:has(.o-bemade-ConvertHeic)`,
      run() {
        this.anchor.querySelector(".o-bemade-ConvertHeic").click();
      },
    },
    {
      content: "A bilingual error notification is shown",
      trigger:
        '.o_notification:contains("Ce fichier HEIC n\'a pas pu être converti"):contains("This HEIC file could not be converted")',
    },
    {
      content: "No error dialog",
      trigger: "body:not(:has(.o_error_dialog))",
    },
  ],
});
