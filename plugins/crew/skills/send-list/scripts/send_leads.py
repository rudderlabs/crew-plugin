#!/usr/bin/env python3
"""Send a list of people to a Crew webhook.

Each row is one person, known by a linkedin_url or an email. A row with a
linkedin_url is a LinkedIn lead, as before: it needs a name, and its profile URL
is its identity. A row with only an email is known by that email; a name is
optional.

A rudderstack-format webhook (the default) gets one identify and one track per
lead. The identify carries what Crew takes the recipient from: a LinkedIn lead's
profile URL as an external id (HeyReach), and an email as traits.email, which
becomes the person's profile email (Customer.io). The track is the event the
Agent triggers on; every column except name, linkedin_url and id becomes one of
its properties, so anything in the file can end up in a message. A
company_domain column nests the identify's company as {name, domain}, which
account research needs. All identifies go first, then a short pause, then the
tracks, so each lead's profile URL or email is stored before the Agent decides
on them.

A list of accounts, one row per company and no person, is sent with
--entity account. Each row needs a company_domain (a bare domain; a scheme,
www. or path is stripped) and may carry company, the name; it is keyed
account:<domain>, its identify carries company {name, domain}, which is what
Crew's account research resolves the company from, and every other column
becomes an event property. A row that also names a person (a linkedin_url or
an email) is refused: send it in person mode. A free-mail domain is refused
too, since no research can resolve a company from it. This is the mode the
expand-audience skill's Expand Agent triggers on.

An id column is the person's user id. Set it when the person already exists in
Crew under another id (a product user id, for example), so the list joins what
Crew already knows about them. Without it a LinkedIn lead is linkedin:<slug> and
an email-only row is the email, lowercased.

A custom-format webhook gets one event per lead built from --body, a JSON
template written to match the webhook's mapping. In it the string "$event" is
replaced by the event name, "$id" by the message id, "$row" by all of the lead's
columns as an object, and "$row.<column>" by one column (a blank column drops
its key).

Message ids are built from the event, the pass and the lead, so sending the same
pass again is a duplicate Crew ignores, and a new pass (shadow, then live) is
new events.

  send_leads.py --file leads.csv --event "ABC Launch Lead" --check
  send_leads.py --env ~/crew-lists/webhooks/<id>.env --file leads.csv --event "ABC Launch Lead" --pass shadow
  send_leads.py --env ~/crew-lists/webhooks/<id>.env --body body.json --file leads.csv --event "ABC Lead" --pass shadow
  send_leads.py --env ~/crew-lists/webhooks/<id>.env --file accounts.csv --event "ABC Account Seeded" --entity account --pass shadow

The destination comes only from --env, except with --check: the webhook's
KEY=VALUE file, which must sit in ~/crew-lists/webhooks/ and be readable by you
alone. It holds either CREW_INGEST_URL, the webhook's RudderStack ingest URL with
the write key in it, sent with no auth header; or CREW_WEBHOOK_URL (the full
.../webhook/<id>/events URL) with CREW_WEBHOOK_TOKEN. The URL must be https
(plain http only to this machine). The script prints the host before it sends
and never follows a redirect, so the list and the token go only to that host.
Python 3.8+, standard library only.
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROFILE = re.compile(r"^(?:https?://)?(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/in/([^/?#\s]+)/?(?:[?#].*)?$", re.I)
# The email pattern Crew's Customer.io channel checks a recipient with (Zod's default `z.email()`).
# A looser check would send an address the send then refuses, and with an `id` the identify would
# overwrite a profile email that worked. assets/review.html carries the same pattern.
EMAIL = re.compile(r"^(?:[A-Za-z0-9_'+\-]+\.)*[A-Za-z0-9_'+\-]*[A-Za-z0-9_+-]@(?:[A-Za-z0-9][A-Za-z0-9\-]*\.)+[A-Za-z]{2,}$")
# The characters Crew accepts in an event name. Any other character is a 400 for every row, so
# the script refuses the name before it sends anything.
EVENT = re.compile(r"^[A-Za-z0-9 _:./-]{1,512}$")
RESERVED = {"name", "linkedin_url", "id"}
# A company domain as a bare host: a scheme, www. and a path are stripped, the rest must look like
# a hostname with a top-level domain. No public-suffix list (standard library only), so a subdomain
# is its own account: app.acme.com and acme.com are two rows. Crew's account research reads the
# value from the identify's company.domain.
DOMAIN = re.compile(r"^(?:https?://)?(?:www\.)?([a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)*\.[a-z]{2,})(?:[/?#].*)?$")
# Research cannot resolve a company from a free-mail domain, so an account row naming one is refused
# before it costs a decision. The same list the website-accounts recipe drops.
FREE_MAIL = {"gmail.com", "googlemail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
             "live.com", "aol.com", "proton.me", "protonmail.com", "qq.com", "163.com"}
WEBHOOKS = "~/crew-lists/webhooks"
LOCAL = {"localhost", "127.0.0.1", "::1"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would carry the list and the token to wherever it points, so it becomes a failed call."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


OPEN = urllib.request.build_opener(NoRedirect).open


def destination(url):
    """The host to send to, or None unless the URL is https (plain http only to this machine)."""
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
    except ValueError:
        return None
    if host and (parts.scheme == "https" or (parts.scheme == "http" and host in LOCAL)):
        return host
    return None


def load(path):
    """(rows, the file's row number of the first lead): a CSV's header is row 1."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        is_json = path.lower().endswith(".json")
        rows = json.load(f) if is_json else list(csv.DictReader(f))
    return [{str(k).strip().lower(): v for k, v in row.items() if k} for row in rows], 1 if is_json else 2


def text(value):
    return value.strip() if isinstance(value, str) else value


def prepare(rows, first, entity="person", keyed="slug"):
    """(leads, problems): leads are ready to send, problems are (row number, reason). Each lead
    carries its kind: linkedin, email, or account. keyed="profile" gives a LinkedIn lead without an
    id the canonical profile URL as its user id, the key a custom mapping mints a found person
    under, so the same person reached both ways is one person in Crew."""
    if entity == "account":
        return prepare_accounts(rows, first)
    leads, problems, seen = [], [], {}
    for n, row in enumerate(rows, start=first):
        name = text(row.get("name") or "")
        url = text(str(row.get("linkedin_url") or ""))
        email = text(str(row.get("email") or ""))
        if url:
            # A LinkedIn lead, as before. A malformed URL is skipped, never sent by its email
            # instead: a HeyReach Agent would get a lead it has no profile to send to.
            match = PROFILE.match(url)
            if not name:
                problems.append((n, "no name"))
                continue
            if not match:
                problems.append((n, "linkedin_url is not a linkedin.com/in/ profile"))
                continue
            key = f"linkedin:{match.group(1).lower()}"
            url = f"https://www.linkedin.com/in/{match.group(1)}"
            kind = "linkedin"
        elif email:
            if not EMAIL.match(email):
                problems.append((n, "email is not an address Customer.io accepts"))
                continue
            key = email.lower()
            kind = "email"
        else:
            problems.append((n, "no linkedin_url or email"))
            continue
        if key in seen:
            problems.append((n, f"same person as row {seen[key]}"))
            continue
        seen[key] = n
        user_id = str(text(row.get("id") or "") or (url if keyed == "profile" and url else key))
        ref = key if url and user_id == url else user_id
        props = {}
        for key, value in row.items():
            value = text(value)
            if key in RESERVED or value in (None, ""):
                continue
            if key == "is_connection" and isinstance(value, str):
                value = value.lower() in ("true", "yes", "1")
            props[key] = value
        traits = {"name": name, "firstName": name.split()[0]} if name else {}
        if EMAIL.match(email):
            # The profile email Crew sends a Customer.io message to. Only an identify writes it.
            traits["email"] = email
        traits.update({k: props[k] for k in ("title", "company") if k in props})
        if props.get("company_domain"):
            # Nested, as the RudderStack identify spec has it: Crew's account research resolves the
            # company from company.domain (or company.website) or an email, never from a name alone.
            traits["company"] = {k: v for k, v in (("name", props.get("company")), ("domain", props["company_domain"])) if v}
        row_values = {**{k: v for k, v in (("name", name), ("linkedin_url", url)) if v}, **props}
        leads.append({"kind": kind, "user_id": user_id, "ref": ref, "url": url or None, "email": email.lower() or None,
                      "traits": traits, "props": props, "row": row_values})
    return leads, problems


def prepare_accounts(rows, first):
    """Account mode: one lead per company, keyed account:<domain>, with no person in it."""
    leads, problems, seen = [], [], {}
    for n, row in enumerate(rows, start=first):
        if text(str(row.get("linkedin_url") or "")) or text(str(row.get("email") or "")):
            problems.append((n, "names a person (linkedin_url or email): send it in person mode, not --entity account"))
            continue
        raw = text(str(row.get("company_domain") or "")).lower()
        match = DOMAIN.match(raw) if raw else None
        if not match:
            problems.append((n, "no company_domain, or not a bare domain like acme.com"))
            continue
        domain = match.group(1)
        if domain in FREE_MAIL:
            problems.append((n, f"{domain} is a free-mail domain, not a company"))
            continue
        if domain in seen:
            problems.append((n, f"same company as row {seen[domain]}"))
            continue
        seen[domain] = n
        # Always the namespaced key, whatever the row says: an id column could equal a
        # person's user id, and the key names the account's window and its counts.
        user_id = f"account:{domain}"
        props = {}
        for column, value in row.items():
            value = text(value)
            if value in (None, ""):
                continue
            props[column] = value
        props["company_domain"] = domain
        company = {k: v for k, v in (("name", props.get("company")), ("domain", domain)) if v}
        leads.append({"kind": "account", "user_id": user_id, "url": None, "email": None,
                      "traits": {"company": company}, "props": props, "row": dict(props)})
    return leads, problems


def window(leads, skip, limit):
    """The leads to send: the first `skip` valid ones left out, then at most `limit`."""
    leads = leads[skip:]
    return leads if limit is None else leads[:limit]


def lead_ref(lead):
    """The lead in key material. A LinkedIn lead and an account keep their readable ids (a LinkedIn
    lead keyed by its profile URL keeps linkedin:<slug>). An email-keyed lead's id is an address,
    and Crew puts the anonymous id in its session key and the message id in its dedup key, so it
    goes hashed, the way Crew hashes a personal identifier it falls back on."""
    if lead["kind"] in ("linkedin", "account"):
        return lead.get("ref") or lead["user_id"]
    return hashlib.sha256(lead["user_id"].encode()).hexdigest()[:32]


def message_key(event, run, lead):
    return f"{re.sub(r'[^a-z0-9]+', '-', event.lower()).strip('-')}-{run}-{lead_ref(lead)}"


def anonymous_id(lead):
    return f"lead-{lead_ref(lead)}"


def payloads(lead, event, identifier, run):
    base = {"userId": lead["user_id"], "anonymousId": anonymous_id(lead)}
    key = message_key(event, run, lead)
    identify = dict(base, type="identify", messageId=f"{key}-identify", traits=lead["traits"])
    if lead["url"]:
        identify["context"] = {"externalId": [{"type": identifier, "id": lead["url"]}]}
    track = dict(base, type="track", event=event, messageId=f"{key}-track", properties=lead["props"])
    return identify, track


MISSING = object()


def fill(template, lead, event, run):
    """The --body template with its "$event", "$id", "$row" and "$row.<column>" strings filled in."""
    if isinstance(template, dict):
        filled = {k: fill(v, lead, event, run) for k, v in template.items()}
        return {k: v for k, v in filled.items() if v is not MISSING}
    if isinstance(template, list):
        return [v for v in (fill(item, lead, event, run) for item in template) if v is not MISSING]
    if template == "$event":
        return event
    if template == "$id":
        return message_key(event, run, lead)
    if template == "$row":
        return lead["row"]
    if isinstance(template, str) and template.startswith("$row."):
        value = lead["row"].get(template[5:].lower())
        return MISSING if value in (None, "") else value
    return template


def read_env(path):
    """KEY=VALUE lines from the webhook's env file (blank lines, comments and `export ` allowed).
    Raises ValueError unless the file sits in ~/crew-lists/webhooks/ and only its owner, you, can
    read it: the file decides where the list goes."""
    real = os.path.realpath(os.path.expanduser(path))
    if os.path.dirname(real) != os.path.realpath(os.path.expanduser(WEBHOOKS)):
        raise ValueError(f"--env must be a file in {WEBHOOKS}/")
    info = os.stat(real)
    if (hasattr(os, "getuid") and info.st_uid != os.getuid()) or info.st_mode & 0o077:
        raise ValueError(f"{path} must be yours and readable only by you: chmod 600 {path}")
    values = {}
    with open(real, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def post(url, token, body):
    if not destination(url):
        return False, "refused: the URL must be https (plain http only to this machine)"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers=headers)
    for attempt in (1, 2):
        try:
            with OPEN(request, timeout=15) as response:
                # A 2xx alone is not proof the event was taken: a wrong Crew URL lands on the server's
                # SPA fallback, which answers 200 with index.html. Count a 202, or a 2xx whose body is
                # empty, JSON, or (from the RudderStack data plane, which answers "OK") plain text.
                body, kind = response.read().strip(), response.headers.get_content_type()
                if response.status == 202 or (200 <= response.status < 300 and kind != "text/html"):
                    return True, str(response.status)
                return False, f"{response.status} {kind}, not a webhook answer: check the URL"
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == 2:
                return False, f"HTTP {err.code}"
        except urllib.error.URLError as err:
            if attempt == 2:
                return False, str(err.reason)
        time.sleep(2)
    return False, "unreachable"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", required=True, help="leads as CSV or JSON")
    parser.add_argument("--event", required=True, help='the trigger event, e.g. "ABC Launch Lead"')
    parser.add_argument("--identifier", default="linkedin_url",
                        help="the HeyReach channel's recipient identifier, for LinkedIn leads; email rows need none")
    parser.add_argument("--pass", dest="run", default="shadow", help="shadow, live, ...: part of every message id")
    parser.add_argument("--skip", type=int, default=0, help="leave out the first N valid leads, e.g. a sample already sent")
    parser.add_argument("--limit", type=int, help="send only the first N valid leads (after --skip)")
    parser.add_argument("--check", action="store_true", help="validate and show one example, send nothing")
    parser.add_argument("--env", help="the webhook's file in ~/crew-lists/webhooks/: CREW_INGEST_URL, "
                        "or CREW_WEBHOOK_URL and CREW_WEBHOOK_TOKEN")
    parser.add_argument("--body", help="JSON template for a custom-format webhook: one event per lead")
    parser.add_argument("--entity", choices=("person", "account"), default="person",
                        help="person (default): one row per person; account: one row per company, keyed by company_domain")
    parser.add_argument("--only", help="send only the lead whose profile slug, email, domain or id is this")
    parser.add_argument("--key", dest="keyed", choices=("slug", "profile"), default="slug",
                        help="slug (default): a LinkedIn lead without an id is keyed linkedin:<slug>; "
                             "profile: by its canonical profile URL, the key a loopback mapping mints a found person under")
    args = parser.parse_args()
    if not EVENT.match(args.event):
        print(f'--event "{args.event}": Crew takes only letters, digits, spaces and _ : . / - in an event name',
              file=sys.stderr)
        return 2

    template = None
    if args.body:
        with open(os.path.expanduser(args.body), encoding="utf-8") as f:
            template = json.load(f)
    leads, problems = prepare(*load(args.file), entity=args.entity, keyed=args.keyed)
    for n, reason in problems:
        print(f"row {n}: skipped, {reason}")
    if args.only:
        want = args.only.lower()
        leads = [lead for lead in leads
                 if want in (lead["user_id"].lower(), (lead["url"] or "").rsplit("/", 1)[-1].lower(), lead["email"],
                             lead["props"].get("company_domain") if lead["kind"] == "account" else None)]
    leads = window(leads, skip=args.skip, limit=args.limit)
    if args.entity == "account":
        print(f"{len(leads)} accounts ready, {len(problems)} skipped")
    else:
        by_email = sum(1 for lead in leads if not lead["url"])
        print(f"{len(leads)} leads ready ({len(leads) - by_email} by LinkedIn profile, {by_email} by email), "
              f"{len(problems)} skipped")

    def build(lead):
        if template is not None:
            return (fill(template, lead, args.event, args.run),)
        return payloads(lead, args.event, args.identifier, args.run)

    if args.check:
        if leads:
            print(json.dumps(build(leads[0]), indent=2))
        return 0
    if not args.env:
        print(f"--env is required to send: the webhook's file in {WEBHOOKS}/", file=sys.stderr)
        return 2
    try:
        env = read_env(args.env)
    except (OSError, ValueError) as err:
        print(err, file=sys.stderr)
        return 2
    ingest = env.get("CREW_INGEST_URL")
    url, token = (ingest, None) if ingest else (env.get("CREW_WEBHOOK_URL"), env.get("CREW_WEBHOOK_TOKEN"))
    if not url or not (ingest or token):
        print(f"{args.env} must set CREW_INGEST_URL, or CREW_WEBHOOK_URL and CREW_WEBHOOK_TOKEN", file=sys.stderr)
        return 2
    host = destination(url)
    if not host:
        print(f"the URL in {args.env} must be https (plain http only to this machine)", file=sys.stderr)
        return 2
    noun = "accounts" if args.entity == "account" else "leads"
    print(f'sending {len(leads)} {noun} to {host} as "{args.event}" ({args.run})')

    failed = 0
    batches = [build(lead) for lead in leads]
    if template is not None:
        for lead, (body,) in zip(leads, batches):
            ok, status = post(url, token, body)
            if not ok:
                failed += 1
                print(f"{lead['user_id']}: event failed, {status}")
        print(f"sent {len(leads)} {noun} ({args.run}), {failed} calls failed")
        return 1 if failed else 0
    for step, index in (("identify", 0), ("track", 1)):
        if step == "track" and leads:
            time.sleep(5)  # let the identifies land before any Agent decides
        for lead, pair in zip(leads, batches):
            ok, status = post(url, token, pair[index])
            if not ok:
                failed += 1
                print(f"{lead['user_id']}: {step} failed, {status}")
    print(f"sent {len(leads)} {noun} ({args.run}), {failed} calls failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
