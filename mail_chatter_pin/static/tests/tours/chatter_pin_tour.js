import {registry} from "@web/core/registry";

const NOTE = ".o-mail-Message:contains('Synthetic tour note')";

registry.category("web_tour.tours").add("mail_chatter_pin_tour", {
  steps: () => [
    {
      content: "The note is in the chatter, nothing is pinned yet",
      trigger: `.o-mail-Chatter ${NOTE}`,
    },
    {
      trigger: ".o-mail-Chatter:not(:has(.o-mail-ChatterPinned))",
    },
    {
      content: "Open the note's actions",
      trigger: `${NOTE}`,
      run: "hover",
    },
    {
      trigger: `${NOTE} [title='Expand']`,
      run: "click",
    },
    {
      content: "Pin it",
      trigger: ".o-dropdown-item:contains('Pin')",
      run: "click",
    },
    {
      content: "The pinned block shows it",
      trigger:
        ".o-mail-ChatterPinned[data-count='1'] .o-mail-ChatterPinned-title:contains('Pinned (1)')",
    },
    {
      trigger: ".o-mail-ChatterPinned-item:contains('Synthetic tour note')",
    },
    {
      content: "The note keeps its place, with a pin marker",
      trigger: `${NOTE} .o-mail-Message-chatterPinned`,
    },
    {
      content: "Unpin from the block",
      trigger: ".o-mail-ChatterPinned-unpin",
      run: "click",
    },
    {
      content: "The block is gone",
      trigger: ".o-mail-Chatter:not(:has(.o-mail-ChatterPinned))",
    },
    {
      trigger: `${NOTE}:not(:has(.o-mail-Message-chatterPinned))`,
    },
  ],
});

registry.category("web_tour.tours").add("mail_chatter_pin_readonly_tour", {
  steps: () => [
    {
      content: "A read-only user sees the pinned block",
      trigger:
        ".o-mail-ChatterPinned[data-count='1'] .o-mail-ChatterPinned-item:contains('Synthetic tour note')",
    },
    {
      content: "but no Unpin link",
      trigger: ".o-mail-ChatterPinned:not(:has(.o-mail-ChatterPinned-unpin))",
    },
    {
      trigger: `${NOTE}`,
      run: "hover",
    },
    {
      trigger: `${NOTE} [title='Expand']`,
      run: "click",
    },
    {
      content: "and no Pin/Unpin action on the message",
      trigger: ".o-dropdown--menu .o-dropdown-item",
    },
    {
      trigger:
        "body:not(:has(.o-dropdown-item:contains('Unpin'))):not(:has(.o-dropdown-item:contains('Pin')))",
    },
  ],
});
