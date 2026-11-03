An optional, prototype "thread view" of a conversation: the messages laid out
like an email thread (oldest first), with Reply and Forward on each message and
at the bottom of the thread.

* A "Thread view" button on the conversation form opens it; a "Form view"
  button goes back. The form stays the default and the fallback; nothing is
  written by switching views.
* Reply opens the conversation's shared reply draft in a pop-up (the same
  mechanism as the chatter Reply of `conversation_draft`); Forward opens the
  forward wizard for one message, or for the whole conversation from the bottom
  of the thread.
* Internal notes are shown, marked as notes; "Log note" stays available. No
  native "Send message", Forward or Reply-All is offered.
