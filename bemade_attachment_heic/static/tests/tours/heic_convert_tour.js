import {registry} from "@web/core/registry";

const CARD = ".o-mail-Message .o-mail-AttachmentContainer";

registry.category("web_tour.tours").add("bemade_attachment_heic_convert_tour", {
  steps: () => [
    {
      // The buttons of a card show on hover (opacity), which headless Chrome does not do.
      content: "The HEIC card offers Convert to JPEG",
      trigger: `${CARD}[title='IMG_TOUR.heic'] .o-bemade-ConvertHeic:not(:visible)`,
      run: "click",
    },
    {
      content: "The card now previews the JPEG",
      trigger: `${CARD}[title='IMG_TOUR.jpg'] img.o-mail-AttachmentImage`,
    },
    {
      content: "The corrupt HEIC card offers Convert to JPEG",
      trigger: `${CARD}[title='BROKEN_TOUR.heic'] .o-bemade-ConvertHeic:not(:visible)`,
      run: "click",
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
