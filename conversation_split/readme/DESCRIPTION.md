Split a conversation from a chosen message onward.

Choosing "Split from here" on a message of a conversation S creates a new
conversation N and moves that message and every later message of S into N.

* A split is a **reassignment, not a copy**: the very same `mail.message`
  records (ids, `Message-Id`, author, date, body, tracking values,
  attachments, transport metadata) simply change owner. Nothing is
  duplicated, so a later correspondent reply to a moved message threads
  into N.
* The split posts exactly one internal note on each side
  (`Continued in ...` / `Split from ...`). **No external email is sent**,
  and no follower or participant is notified.
* N carries S's name (or the split message's subject), assignee, team,
  tags and primary transport. Participants and linked records are carried
  by default and may be edited in the wizard before confirming.
* Splitting from the first message is refused: it would leave the original
  conversation empty.
