# Copyright (C) 2026 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
"""A tiny, strict, read-only IMAP server over a real TCP socket.

Test (and demo) fixture only. Unlike an in-process fake client, a real
``imaplib`` talks to it, so the exact bytes the engine puts on the wire --
quoting, literals, the SEARCH charset -- are what get exercised.

Deliberately strict: it only knows the handful of commands the inbox
engine issues (LOGIN, SELECT, UID SEARCH, UID FETCH, LOGOUT) and answers
``BAD`` to anything else, so a regression that sends an unexpected
command (STORE, EXPUNGE, a malformed SEARCH) fails loudly. Every command
line is recorded in ``commands`` so a test can assert nothing mutating
ever ran. Standard library only: it can be run stand-alone for a demo
(``python fake_imap_server.py --port 1143``).

SEARCH supports ``ALL``, a sequence range ``low:high`` and
``[CHARSET UTF-8] TEXT <string|literal>`` (and SUBJECT likewise); TEXT is a case-insensitive
substring match over the decoded headers and body, as on a real server.
Non-ASCII search text without ``CHARSET UTF-8`` is refused, as real
servers do.
"""

import argparse
import email
import email.message
import email.policy
import re
import socketserver
import sys
import threading
import time

_LITERAL_RE = re.compile(rb"\{(\d+)\+?\}$")
_PLACEHOLDER_RE = re.compile(rb"\x00(\d+)\x00")


class FakeImapServer:
    """``FakeImapServer([raw_rfc822_bytes, ...])``; UID == sequence number
    (1-based, oldest first). ``start()`` returns the port."""

    def __init__(self, messages, login="user@example.com", password="secret"):
        self.messages = list(messages)
        self.login = login
        self.password = password
        self.commands = []
        self.search_terms = []  # decoded TEXT/SUBJECT values received
        self._server = None
        self._parsed = [
            email.message_from_bytes(raw, policy=email.policy.default)
            for raw in self.messages
        ]

    # -- lifecycle ---------------------------------------------------
    def start(self, host="127.0.0.1", port=0):
        outer = self

        class Handler(_Handler):
            fixture = outer

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        self._server = Server((host, port), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self._server.server_address[1]

    def stop(self):
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None

    # -- search ------------------------------------------------------
    def _haystack(self, index):
        parsed = self._parsed[index]
        parts = [str(parsed.get(h, "")) for h in ("From", "To", "Cc", "Subject")]
        body = parsed.get_body(preferencelist=("plain", "html"))
        parts.append(body.get_content() if body else "")
        return "\n".join(parts).casefold()

    def search_text(self, text, subject_only=False):
        needle = text.casefold()
        return [
            i + 1
            for i in range(len(self.messages))
            if needle
            in (
                str(self._parsed[i].get("Subject", "")).casefold()
                if subject_only
                else self._haystack(i)
            )
        ]


class _Handler(socketserver.StreamRequestHandler):
    fixture = None

    def _send(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.wfile.write(data)
        self.wfile.flush()

    def _read_command(self):
        """One command line with its literals resolved into placeholders."""
        line = self.rfile.readline()
        if not line:
            return None, []
        line = line.rstrip(b"\r\n")
        literals = []
        while True:
            match = _LITERAL_RE.search(line)
            if not match:
                break
            self._send(b"+ go ahead\r\n")
            literals.append(self.rfile.read(int(match.group(1))))
            line = (
                line[: match.start()]
                + b"\x00%d\x00" % (len(literals) - 1)
                + self.rfile.readline().rstrip(b"\r\n")
            )
        return line, literals

    def handle(self):
        fx = self.fixture
        selected = False
        self._send("* OK IMAP4rev1 fake server ready\r\n")
        while True:
            line, literals = self._read_command()
            if line is None:
                return
            fx.commands.append(line)
            tag, _, rest = line.partition(b" ")
            tag = tag.decode()
            verb, _, args = rest.partition(b" ")
            verb = verb.upper()
            if verb == b"CAPABILITY":
                self._send("* CAPABILITY IMAP4rev1\r\n%s OK done\r\n" % tag)
            elif verb == b"LOGIN":
                ok = args.split(b" ")[0].strip(b'"').decode() == fx.login
                self._send("%s %s\r\n" % (tag, "OK logged in" if ok else "NO denied"))
            elif verb == b"SELECT":
                selected = True
                self._send(
                    "* %d EXISTS\r\n%s OK [READ-WRITE] selected\r\n"
                    % (len(fx.messages), tag)
                )
            elif verb == b"LOGOUT":
                self._send("* BYE bye\r\n%s OK logout\r\n" % tag)
                return
            elif verb == b"UID" and selected:
                sub, _, sub_args = args.partition(b" ")
                if sub.upper() == b"SEARCH":
                    self._search(tag, sub_args, literals)
                elif sub.upper() == b"FETCH":
                    self._fetch(tag, sub_args)
                else:
                    self._send("%s BAD unsupported UID command\r\n" % tag)
            else:
                self._send("%s BAD unsupported command\r\n" % tag)

    def _search(self, tag, args, literals):
        fx = self.fixture
        tokens = args.split()
        charset = None
        if tokens and tokens[0].upper() == b"CHARSET":
            charset = tokens[1].upper()
            tokens = tokens[2:]
        if charset not in (None, b"UTF-8"):
            self._send("%s NO [BADCHARSET (UTF-8)] unsupported\r\n" % tag)
            return
        if len(tokens) == 1 and tokens[0].upper() == b"ALL":
            hits = list(range(1, len(fx.messages) + 1))
        elif len(tokens) == 1 and re.fullmatch(rb"\d+:\d+", tokens[0]):
            low, high = (int(n) for n in tokens[0].split(b":"))
            hits = [n for n in range(low, high + 1) if n <= len(fx.messages)]
        elif len(tokens) == 2 and tokens[0].upper() in (b"TEXT", b"SUBJECT"):
            raw = tokens[1]
            placeholder = _PLACEHOLDER_RE.fullmatch(raw)
            if placeholder:
                value = literals[int(placeholder.group(1))]
            elif raw.startswith(b'"') and raw.endswith(b'"'):
                value = raw[1:-1]
            else:
                value = raw
            if charset is None and any(byte > 127 for byte in value):
                self._send("%s BAD non-ASCII search needs CHARSET\r\n" % tag)
                return
            fx.search_terms.append(value.decode("utf-8"))
            hits = fx.search_text(value.decode("utf-8"), tokens[0].upper() == b"SUBJECT")
        else:
            self._send("%s BAD unsupported SEARCH criteria\r\n" % tag)
            return
        listing = b" ".join(b"%d" % n for n in hits)
        self._send(b"* SEARCH " + listing + b"\r\n")
        self._send("%s OK SEARCH completed\r\n" % tag)

    def _fetch(self, tag, args):
        fx = self.fixture
        uid_set, _, spec = args.partition(b" ")
        wanted = [int(n) for n in uid_set.split(b",") if n.strip().isdigit()]
        headers_only = b"HEADER.FIELDS" in spec
        label = spec.strip(b"()").replace(b".PEEK", b"")
        for uid in wanted:
            if not 1 <= uid <= len(fx.messages):
                continue
            raw = fx.messages[uid - 1]
            payload = raw.split(b"\r\n\r\n", 1)[0] + b"\r\n\r\n" if headers_only else raw
            self._send(b"* %d FETCH (UID %d %s {%d}\r\n" % (uid, uid, label, len(payload)))
            self._send(payload + b")\r\n")
        self._send("%s OK FETCH completed\r\n" % tag)


def build_message(subject, sender, body, date, to="desk@example.com", n=0):
    """One RFC822 message, CRLF line endings, UTF-8 where needed."""
    msg = email.message.EmailMessage(policy=email.policy.SMTP)
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = to
    msg["Date"] = date
    msg["Message-Id"] = "<fake-%d@example.com>" % n
    msg.set_content(body)
    return msg.as_bytes()


if __name__ == "__main__":  # stand-alone demo mailbox
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--seconds", type=int, default=3600)
    parser.add_argument("--login", default="user@example.com")
    parser.add_argument("--password", default="secret")
    options = parser.parse_args()
    demo = [
        (
            "Demande de réparation - compresseur",
            "Marie Tremblay <marie@exemple.ca>",
            "Bonjour, le compresseur de l'atelier est en panne.",
            "Mon, 12 Oct 2026 09:00:00 -0400",
        ),
        (
            "Soumission pompe hydraulique",
            "Jean Gagnon <jean@exemple.ca>",
            "Pouvez-vous nous envoyer un prix pour la pompe?",
            "Tue, 13 Oct 2026 10:30:00 -0400",
        ),
        (
            "Facture de septembre",
            "Comptabilité <compta@exemple.ca>",
            "Ci-joint la facture, aucune autre demande.",
            "Wed, 14 Oct 2026 08:15:00 -0400",
        ),
    ]
    server = FakeImapServer(
        [build_message(s, f, b, d, n=i) for i, (s, f, b, d) in enumerate(demo, 1)],
        login=options.login,
        password=options.password,
    )
    sys.stdout.write("%d\n" % server.start(port=options.port))
    sys.stdout.flush()
    time.sleep(options.seconds)
    server.stop()
