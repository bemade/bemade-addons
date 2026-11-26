# Copyright 2026 Bemade Inc. (<https://www.bemade.org>)
# Author: Denis Durepos <denis@bemade.org>
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0.html).
{
    'name': 'Bemade Portal Kit: Chat',
    'version': '19.0.1.1.0',
    'category': 'Website/Portal',
    'summary': 'Portal conversations on Discuss: direct chats and managed announcement groups, '
               'a floating window and e-mail notices each user chooses.',
    'description': """
Bemade Portal Kit: Chat
=======================

Conversations between PEOPLE (not records) in the portal app, stored as
native Discuss channels:

* a direct chat is a ``discuss.channel`` of type ``chat`` (one per pair:
  portal and portal, or portal and internal), made by
  ``_get_or_create_chat``;
* a managed group is a ``group`` channel the consumer keeps in sync
  (membership only: no self-join, no ``group_public_id``), for
  announcements: its posters post, its readers may only reply to a message.

Internal users see whatever vanilla Discuss shows them (they find every
portal user in « start a conversation » and in the invite dialog, and the
avatar card's « Send message » works for portal users). The PORTAL UI talks
only to the kit routes below, which return only what the viewer may see.

The chat is OFF until a consumer turns it on. Who may talk to whom is the
consumer's policy (hooks); the kit does not force any rule.

Hooks (``portal.kit``, extend with ``super()``)
-----------------------------------------------
* ``_pk_chat_enabled(app)``: the chat is on for ``app``. Default: the
  app's registration ``_pk_apps()[app]['chat']`` (``'chat': True``).
* ``_pk_chat_contacts(user)``: the partners ``user`` may START a direct
  chat with (the picker of « New conversation », ``/my/app/chat/start``).
  Per user, never cached. Default: nobody.
* ``_pk_chat_managed_channels()``: ``[{'key': 'team-12', 'name': 'Team
  parents', 'app': 'myapp', 'members': {partner_id: 'poster' |
  'reader'}}]``. Data, never cached; read with
  ``pk_chat_managed_channels(app)``.

Managed channels
----------------
``portal.kit._pk_chat_sync(key=None)`` (public, idempotent) makes the
database match the hook: it creates or renames the group channel of each
key (``discuss.channel.pk_managed_key``, unique), adds and removes members
and sets their role (``discuss.channel.member.pk_role``). It is SILENT: no
« joined » / « invited » posts (the core's ``post_joined_message=False``
path), and a new member starts with the history read and never e-mailed.
A channel whose key the hook no longer returns is archived, never deleted.
A nightly cron runs it; a consumer calls it when its data changes (with
``key`` for one channel).

Roles: a ``poster`` posts; a ``reader`` may only REPLY (a ``comment``
whose parent is a message of the same channel). The rule is on the models,
by uid, so it holds on every route (``message_post``, ``/mail/message/post``,
a raw ``mail.message.create``). Posters and internal users are
unrestricted; reactions stay allowed; authors' names are always shown.
A reader never sees the member list in the portal; a poster does.

Gates on the core (minimal; internal users unchanged)
-----------------------------------------------------
* ``/chat/<id>/<uuid>`` never joins a managed channel;
* ``/discuss/channel/<id>`` sends a share member of a chat / group to the
  kit's conversation page (a managed channel: 404 while the chat is off);
* a share user cannot start or join a call (``_rtc_join_call``);
* a share user cannot create a chat through Discuss
  (``_get_or_create_chat``): the kit route does, after the contacts check;
* Discuss's own mention / ``@everyone`` e-mail to share partners is dropped
  in chats and groups: their e-mails follow the kit's preferences only.

Routes (``auth='user'``, JSON, member check; 404 while the chat is off)
-----------------------------------------------------------------------
``GET /my/app/chat/conversations`` (``{id, kind, title, avatar_url,
preview, author_is_me, when, unread}``, the latest activity first),
``GET /my/app/chat/<id>/messages?before=&after=&limit=`` (comment messages
only: ``{id, author_name, author_avatar_url, body_html, when, own, parent,
can_reply}``; ``members`` for a poster only, never a count for a reader),
``POST /my/app/chat/<id>/post`` (``body`` plain text, ``parent_id``),
``POST /my/app/chat/<id>/read``, ``GET /my/app/chat/contacts?q=``,
``POST /my/app/chat/start`` (``partner_id``; 403 unless a contact),
``GET /my/app/chat/unread`` (``{count}``), the avatars
``/my/app/chat/<id>/avatar[/<partner_id>]`` and the pages
``/my/app/conversations`` and ``/my/app/conversations/<id>`` (the
e-mails' links). No e-mail or phone in any payload. Dates in the viewer's
time zone: the time today, « Yesterday », the weekday within the week,
else day and month (and year).

Portal UI
---------
The app bar's bubble (``data-pk-chat-bubble``: the unread badge, the
conversations, « New conversation » with the kit's picker) and ONE
floating window (``data-pk-chat-window``; docked bottom-right from 992 px,
a full-screen sheet below; it follows the user from page to page through
``sessionStorage``). A reader of a managed channel has no composer: each
message has « Reply ». Enter sends on a laptop (Shift+Enter: a new line).

The block ``bemade_portal_kit_chat.pk_conversation`` shows the same thread
inline on any kit page::

    <t t-call="bemade_portal_kit_chat.pk_conversation">
        <t t-set="channel_id" t-value="channel.id"/>   <!-- or partner_id -->
    </t>

Live updates: Odoo's ``bus_service`` (started by the bubble) only signals
« channel X changed »; the client refetches from the kit routes. Without
the bus, a 20 s poll (backoff, paused while the tab is hidden).

E-mails (kit 1.17 notification preferences)
-------------------------------------------
Kinds: ``chat.direct`` (« Direct messages », default each), and in groups
``chat.announcement`` (« Group announcements ») and ``chat.reply``
(« Replies in groups »), default daily digest. Internal users: off by
default (they have Discuss). « Each »: one e-mail per conversation, at most
every 5 minutes, for messages unread for 10 minutes; « Digest »: one
e-mail at 07:00 in the user's time zone, once per day, listing the unread
conversations; « Never »: nothing.

Phone (version 1.1, kit 1.18)
-----------------------------
With ``bemade_portal_kit_pwa`` (Web Push from the installed app), each of
the three kinds has a phone switch (« On the phone », off by default)
beside its e-mail choice; turning the phone on (« Settings ›
Notifications », or the one-time banner after the user's first message)
switches it on for the three kinds. A share member is pushed only when the
chat is on for their app and the switch of THAT message's kind is on for
them (a reader: announcements and the replies in their own threads, as
for the e-mails). The notification opens ``/my/app/conversations/<id>``;
a group's title is its name and the author, never the members. A message
sent to the phone skips its 10-minute « each » e-mail
(``pk_pushed_message_id``); the daily digest still lists it. No registered
phone: nothing changes. Internal members keep Discuss's own push, payload
and all. The app icon's number is the unread count.

Security note
-------------
The portal controllers hide what a reader may not see. A reader calling
Odoo's own Discuss JSON routes (``/discuss/channel/members``, ``/mail/data``,
mention suggestions) or watching the websocket can still learn member
names of a managed channel. Nothing in the portal UI shows them.
""",
    'author': 'Bemade Inc.',
    'maintainers': ['dureposd'],
    'website': 'https://www.bemade.org',
    'license': 'LGPL-3',
    'depends': ['bemade_portal_kit', 'mail', 'bus'],
    'data': [
        'data/ir_cron.xml',
        'data/mail_templates.xml',
        'views/pk_chat_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'bemade_portal_kit_chat/static/src/scss/pk_chat.scss',
            'bemade_portal_kit_chat/static/src/js/pk_chat_push_prompt.js',
            'bemade_portal_kit_chat/static/src/js/pk_chat_client.js',
            'bemade_portal_kit_chat/static/src/js/pk_chat_window.js',
            'bemade_portal_kit_chat/static/src/js/pk_chat_bubble.js',
        ],
        'web.assets_backend': [
            'bemade_portal_kit_chat/static/src/backend/pk_chat_portal_partners.js',
            'bemade_portal_kit_chat/static/src/backend/pk_chat_palette.js',
            'bemade_portal_kit_chat/static/src/backend/pk_chat_avatar_card.xml',
        ],
        'web.assets_unit_tests_setup': [
            'bemade_portal_kit_chat/static/src/js/pk_chat_push_prompt.js',
            'bemade_portal_kit_chat/static/src/js/pk_chat_client.js',
            'bemade_portal_kit_chat/static/src/js/pk_chat_window.js',
            'bemade_portal_kit_chat/static/src/backend/pk_chat_portal_partners.js',
        ],
        'web.assets_unit_tests': [
            'bemade_portal_kit_chat/static/tests/*.test.js',
        ],
        'web.assets_tests': [
            'bemade_portal_kit_chat/static/tests/tours/*.js',
        ],
    },
    'pre_init_hook': 'pre_init_hook',
    'installable': True,
    'application': False,
}
