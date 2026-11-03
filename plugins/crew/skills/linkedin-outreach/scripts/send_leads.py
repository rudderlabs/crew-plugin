#!/usr/bin/env python3
"""Send LinkedIn leads to a Crew webhook: one identify and one track per lead.

The identify carries the person's LinkedIn profile URL as an external id, which
is the only place Crew takes the recipient from. The track is the event the
Agent triggers on; every column except name, linkedin_url and id becomes one of
its properties, so anything in the file can end up in a message.

All identifies go first, then a short pause, then the tracks, so each lead's
profile URL is stored before the Agent decides on them. Message ids are built
from the event, the pass and the lead, so sending the same pass again is a
duplicate Crew ignores, and a new pass (shadow, then live) is new events.

  send_leads.py --file leads.csv --event "ABC Launch Lead" --check
  send_leads.py --file leads.csv --event "ABC Launch Lead" --pass shadow --limit 20

Needs CREW_WEBHOOK_URL (the full .../webhook/<id>/events URL, https) and
CREW_WEBHOOK_TOKEN in the environment, except with --check: source them from the
webhook's file inside the one command that sends, never as VAR=... on the
command line. It prints the host before it sends and never follows a redirect,
so the token goes only to that host. Python 3.8+, standard library only.
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

PROFILE = re.compile(r"^(?:https?://)?(?:[a-z]{2,3}\.)?(?:www\.)?linkedin\.com/in/([^/?#\s]+)/?(?:[?#].*)?$", re.I)
RESERVED = {"name", "linkedin_url", "id"}
LOCAL = {"localhost", "127.0.0.1", "::1"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect would carry the token to wherever it points, so it becomes a failed call."""

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


def prepare(rows, first):
    """(leads, problems): leads are ready to send, problems are (row number, reason)."""
    leads, problems, seen = [], [], {}
    for n, row in enumerate(rows, start=first):
        name, url = text(row.get("name") or ""), text(row.get("linkedin_url") or "")
        match = PROFILE.match(url or "")
        if not name:
            problems.append((n, "no name"))
            continue
        if not match:
            problems.append((n, "linkedin_url is not a linkedin.com/in/ profile"))
            continue
        slug = match.group(1)
        if slug.lower() in seen:
            problems.append((n, f"same profile as row {seen[slug.lower()]}"))
            continue
        seen[slug.lower()] = n
        user_id = str(text(row.get("id") or "") or f"linkedin:{slug.lower()}")
        props = {}
        for key, value in row.items():
            value = text(value)
            if key in RESERVED or value in (None, ""):
                continue
            if key == "is_connection" and isinstance(value, str):
                value = value.lower() in ("true", "yes", "1")
            props[key] = value
        traits = {"name": name, "firstName": name.split()[0]}
        traits.update({k: props[k] for k in ("title", "company") if k in props})
        leads.append({"user_id": user_id, "url": f"https://www.linkedin.com/in/{slug}", "traits": traits, "props": props})
    return leads, problems


def payloads(lead, event, identifier, run):
    base = {"userId": lead["user_id"], "anonymousId": f"lead-{lead['user_id']}"}
    key = f"{re.sub(r'[^a-z0-9]+', '-', event.lower()).strip('-')}-{run}-{lead['user_id']}"
    identify = dict(base, type="identify", messageId=f"{key}-identify", traits=lead["traits"],
                    context={"externalId": [{"type": identifier, "id": lead["url"]}]})
    track = dict(base, type="track", event=event, messageId=f"{key}-track", properties=lead["props"])
    return identify, track


def post(url, token, body):
    """POST one call. Checked here as well as in main, because seed_profiles.py calls it directly."""
    if not destination(url):
        return False, "refused: the URL must be https (plain http only to this machine)"
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST", headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {token}"})
    for attempt in (1, 2):
        try:
            with OPEN(request, timeout=15) as response:
                return response.status < 300, str(response.status)
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
    parser.add_argument("--identifier", default="linkedin_url", help="the HeyReach channel's recipient identifier")
    parser.add_argument("--pass", dest="run", default="shadow", help="shadow, live, ...: part of every message id")
    parser.add_argument("--limit", type=int, help="send only the first N valid leads")
    parser.add_argument("--check", action="store_true", help="validate and show one example, send nothing")
    args = parser.parse_args()

    leads, problems = prepare(*load(args.file))
    for n, reason in problems:
        print(f"row {n}: skipped, {reason}")
    if args.limit is not None:
        leads = leads[: args.limit]
    print(f"{len(leads)} leads ready, {len(problems)} skipped")
    if args.check:
        if leads:
            print(json.dumps(payloads(leads[0], args.event, args.identifier, args.run), indent=2))
        return 0
    url, token = os.environ.get("CREW_WEBHOOK_URL"), os.environ.get("CREW_WEBHOOK_TOKEN")
    if not url or not token:
        print("set CREW_WEBHOOK_URL and CREW_WEBHOOK_TOKEN first", file=sys.stderr)
        return 2
    host = destination(url)
    if not host:
        print("CREW_WEBHOOK_URL must be an https URL (plain http only to this machine)", file=sys.stderr)
        return 2
    print(f'sending {len(leads)} leads to {host} as "{args.event}" ({args.run})')

    failed = 0
    batches = [payloads(lead, args.event, args.identifier, args.run) for lead in leads]
    for step, index in (("identify", 0), ("track", 1)):
        if step == "track" and leads:
            time.sleep(5)  # let the identifies land before any Agent decides
        for lead, pair in zip(leads, batches):
            ok, status = post(url, token, pair[index])
            if not ok:
                failed += 1
                print(f"{lead['user_id']}: {step} failed, {status}")
    print(f"sent {len(leads)} leads ({args.run}), {failed} calls failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
