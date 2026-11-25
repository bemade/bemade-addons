Shows who a mail sent from a conversation went to.

Each outbound message in a conversation lists its **To** and **Cc**
addresses under the author line, in the conversation's chatter. The lists are
recorded when the message is sent, from the headers that actually went out
(after any transport-side filtering), and never change afterwards.

Blind-copied addresses still receive the mail but are never recorded or
shown. Inbound mail, internal notes and forward notes are unchanged, and no
extra email is produced.
