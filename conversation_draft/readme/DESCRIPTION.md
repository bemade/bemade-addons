Shared reply drafts on top of `conversation_base`.

A reply to a conversation is prepared as a **draft** that everyone who can work
the conversation edits together, live, instead of one person writing it in a
private composer.

- One active draft per conversation (enforced in the database), kept when the
  conversation is reassigned.
- The body is a collaborative HTML field: co-editors see each other's edits,
  cursors and presence without a reload. Review comments are the draft's own
  chatter and never notify an external party.
- Recipients carry a To/Cc/Bcc mode, pre-filled from the conversation's external
  participants; a participant without an address stays visible and is flagged.
  Bcc never leaks back into the conversation.
- Pick a mail template to seed the draft, or insert it after the text already
  there.
- Sending goes through the conversation's own reply seam and is exactly-once in
  every non-crash path: the draft is claimed with a committed compare-and-set
  before the email leaves, so a retried request can never send twice. A send
  stuck for ten minutes can be marked as sent or returned to draft by hand.

The module is opt-in: nothing changes on a conversation until a user clicks
**Reply**. Access to a draft always follows access to its conversation.
