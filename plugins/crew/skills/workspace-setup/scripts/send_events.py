#!/usr/bin/env python3
"""Send test events to a Crew webhook, or turn them into a dry-run list.

The input is a JSON file (or - for stdin) holding a list of RudderStack-shaped
calls, or an object with an "events" list: track, identify, page or screen, each
with a userId or an anonymousId. Every call is checked before anything is sent,
and one bad call stops the whole run, because Crew answers it with a 400 and a
RudderStack-format webhook keeps nothing from it:

  - a track needs an "event" name of letters, digits, spaces and _ : . / - only
  - a userId or anonymousId that is a number is sent as text
  - group and alias calls are refused here: Crew ignores them

Identify calls go first, then a pause, then everything else in file order, so
each person's traits (name, email) are on their profile before an Agent decides
on them. A track's context.traits are never read by Crew; the script says so.

originalTimestamp is stamped with the moment each call is sent, in UTC, unless
--keep-timestamps is given (for replaying real history); a kept timestamp must
be a full ISO 8601 time with a zone. Each call's messageId is built from --run,
its place in the file and its content, so sending the same file again is a
duplicate Crew ignores: pass a new --run to send it again as new events.
--keep-ids keeps each call's own messageId instead.

  send_events.py --file events.json --check
  send_events.py --file events.json --try-event
  send_events.py --env ~/crew-lists/webhooks/<webhookId>.env --file events.json --run test-1

--check validates and prints the first call as it would be sent. --try-event
prints the track calls as the `event` list for preview_tryEvent (at most 10):
a dry run has no profile, so each person's identify traits are copied into the
event's properties and their email and phone into identifiers. Neither needs a
webhook.

Sending needs the webhook's URL and bearer token: CREW_WEBHOOK_URL and
CREW_WEBHOOK_TOKEN, from --env (a KEY=VALUE file under ~/crew-lists/webhooks/,
owned by you and readable only by you) or from the environment. The token is
never an argument. Redirects are refused, so the token never goes to another
host. One line per call, then a summary. Exit 0 when at least one call was
accepted and none failed; 1 when any call failed, or when every call was a
duplicate; 2 when the file or the setup is wrong. Python 3.8+, standard library
only.
"""

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

# Crew's ingest charset for event names (the event-ingestion schema in Crew's shared package).
EVENT = re.compile(r"^[A-Za-z0-9 _:./-]{1,512}$")
# A full ISO 8601 time with a zone, the shape Crew's ingest accepts for originalTimestamp.
ZONED = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
SENT_TYPES = {"track", "identify", "page", "screen"}
IGNORED_TYPES = {"group", "alias"}
TRY_EVENT_MAX = 10
MAX_ID = 512
TEST_DOMAINS = re.compile(r"@(?:[^@]+\.)?(?:example\.(?:com|org|net)|[^@]+\.(?:test|example|invalid))$", re.I)
ENV_DIR = os.path.join(os.path.expanduser("~"), "crew-lists", "webhooks")


def note(text):
    print(f"note: {text}", file=sys.stderr)


def reject_constant(name):
    raise ValueError(f"{name} is not valid JSON for Crew")


def load(path):
    if path == "-":
        data = json.load(sys.stdin, parse_constant=reject_constant)
    else:
        with open(os.path.expanduser(path), encoding="utf-8-sig") as f:
            data = json.load(f, parse_constant=reject_constant)
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        data = data["events"]
    if not isinstance(data, list):
        raise ValueError('the file must hold a JSON list of calls, or an object with an "events" list')
    return data


def as_text(value):
    """A number id as text (42 and 42.0 both become "42"); anything else unchanged."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return str(int(value))
    return value


def zoned_instant(stamp):
    """True when stamp is an ISO 8601 time with a zone that names a real instant (2026-02-31T09:00:00Z does not)."""
    if not isinstance(stamp, str) or not ZONED.match(stamp):
        return False
    # Python 3.8's fromisoformat takes no Z and only 3 or 6 fraction digits; the
    # shape is already fixed by ZONED, so this only asks whether the calendar
    # and clock values exist.
    normalised = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], stamp.replace("Z", "+00:00"))
    try:
        datetime.fromisoformat(normalised)
    except ValueError:
        return False
    return True


def who(call):
    return call.get("userId") or call.get("anonymousId") or "?"


def describe(call):
    kind = call["type"]
    name = f' "{call["event"]}"' if kind == "track" else ""
    return f"{kind}{name} {who(call)}"


def check_call(n, call, keep_timestamps, keep_ids):
    """The problem with this call, or None. Normalises ids and the type in place."""
    kind = call.get("type", "track")
    if not isinstance(kind, str):
        return f"call {n}: type must be text"
    call["type"] = kind
    if kind in IGNORED_TYPES:
        return f"call {n}: Crew ignores {kind} calls; send account facts as track properties instead"
    if kind not in SENT_TYPES:
        return f'call {n}: type "{kind}" is not track, identify, page or screen'
    for key in ("userId", "anonymousId"):
        if call.get(key) is None:
            call.pop(key, None)
            continue
        call[key] = as_text(call[key])
        if not isinstance(call[key], str) or len(call[key]) > MAX_ID:
            return f"call {n}: {key} must be text of at most {MAX_ID} characters"
    if not (call.get("userId") or call.get("anonymousId")):
        return f"call {n}: needs a userId or an anonymousId"
    if kind == "track":
        event = call.get("event")
        if not isinstance(event, str) or not EVENT.match(event):
            return f"call {n}: event {json.dumps(event)} must be letters, digits, spaces and _ : . / - only"
    elif "event" in call:
        return f'call {n}: a {kind} call carries no event name; remove "event" or make it a track'
    for key in ("properties", "context", "traits"):
        if key in call and not isinstance(call[key], dict):
            return f"call {n}: {key} must be an object"
    if keep_timestamps and "originalTimestamp" in call:
        # An absent timestamp lets Crew stamp the arrival; an explicit null is
        # refused by Crew with a 400, so it is a problem here, not a blank.
        stamp = call["originalTimestamp"]
        if stamp is None:
            return f"call {n}: originalTimestamp is null; remove it to stamp the arrival, or give it a time"
        if not zoned_instant(stamp):
            return f"call {n}: originalTimestamp {json.dumps(stamp)} is not an ISO 8601 time with a zone, or not a real time"
    if keep_ids:
        mid = call.get("messageId")
        if not isinstance(mid, str) or not mid.strip() or len(mid) > MAX_ID:
            return f"call {n}: --keep-ids needs a messageId of 1 to {MAX_ID} characters on every call"
    return None


def prepare(raw, keep_timestamps, keep_ids):
    """(calls, problems): calls are ready to send; any problem stops the run."""
    calls, problems = [], []
    for n, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            problems.append(f"call {n}: not a JSON object")
            continue
        call = dict(item)
        problem = check_call(n, call, keep_timestamps, keep_ids)
        if problem:
            problems.append(problem)
            continue
        context = call.get("context") or {}
        if call["type"] == "track" and isinstance(context.get("traits"), dict) and context["traits"]:
            note(f"call {n}: a track's context.traits are never read; send them in an identify")
        traits = call.get("traits") or context.get("traits") or {}
        email = traits.get("email") if isinstance(traits, dict) else None
        if isinstance(email, str) and email and not TEST_DOMAINS.search(email):
            note(f"call {n}: {email} looks like a real address; test people should use @example.com")
        calls.append(call)
    return calls, problems


def message_id(call, run, position):
    body = {k: v for k, v in call.items() if k not in ("messageId", "sentAt")}
    material = json.dumps([run, position, body], sort_keys=True)
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
    return f"{re.sub(r'[^a-z0-9]+', '-', run.lower()).strip('-') or 'run'}-{digest}"


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def try_event_list(calls):
    """The track calls as preview_tryEvent `event` entries."""
    traits_by_person = {}
    for call in calls:
        if call["type"] == "identify":
            traits = call.get("traits") or (call.get("context") or {}).get("traits") or {}
            traits_by_person.setdefault(who(call), {}).update(traits)
    entries = []
    for call in calls:
        if call["type"] != "track":
            continue
        traits = traits_by_person.get(who(call), {})
        properties = {k: v for k, v in traits.items() if k not in ("email", "phone")}
        properties.update(call.get("properties") or {})
        entry = {"eventName": call["event"], "eventType": "track", "properties": properties}
        if call.get("userId"):
            entry["userId"] = call["userId"]
        if call.get("anonymousId"):
            entry["anonymousId"] = call["anonymousId"]
        context = {k: v for k, v in (call.get("context") or {}).items() if k != "traits"}
        if context:
            entry["context"] = context
        ids = {k: str(traits[k]) for k in ("email", "phone") if traits.get(k)}
        if ids:
            entry["identifiers"] = ids
        entries.append(entry)
    return entries


def read_env(path):
    """KEY=VALUE lines from a webhook env file kept where the plugin's scripts look for one."""
    full = os.path.realpath(os.path.expanduser(path))
    if os.path.dirname(full) != os.path.realpath(ENV_DIR) or not full.endswith(".env"):
        raise ValueError(f"--env must be a .env file directly in {ENV_DIR}")
    info = os.stat(full)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError(f"{full} must be a file you own, readable only by you (chmod 600)")
    values = {}
    with open(full, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export "):]
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    return values


def check_url(url):
    parts = urllib.parse.urlparse(url or "")
    local = parts.hostname in ("localhost", "127.0.0.1")
    if parts.scheme != "https" and not (parts.scheme == "http" and local):
        return "CREW_WEBHOOK_URL must be an https URL"
    if not re.search(r"/webhook/[^/]+/events/?$", parts.path):
        return "CREW_WEBHOOK_URL must end in /webhook/<id>/events, the url webhooks_create returned"
    return None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # following one would carry the bearer token to wherever it points


OPENER = urllib.request.build_opener(NoRedirect)


def answer_fields(text, token):
    """Crew's own answer fields only, never a whole body, and never the token."""
    try:
        data = json.loads(text) if text else {}
    except ValueError:
        return "(not a Crew answer)"
    if not isinstance(data, dict):
        return "(not a Crew answer)"
    parts = [str(data[k]) for k in ("status", "error", "reason", "details") if data.get(k) not in (None, "")]
    out = "; ".join(parts)[:200]
    return out.replace(token, "***") if token else out


def post(url, token, body):
    """(outcome, status line): outcome is accepted, duplicate or failed."""
    data = json.dumps(body).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}
    for attempt in (1, 2):
        request = urllib.request.Request(url, data=data, method="POST", headers=headers)
        try:
            with OPENER.open(request, timeout=20) as response:
                text = response.read().decode("utf-8", "replace").strip()
                try:
                    status = json.loads(text).get("status") if text else None
                except (ValueError, AttributeError):
                    status = None
                if response.status == 202 and status == "accepted":
                    return "accepted", "202 accepted"
                if response.status == 200 and status == "duplicate":
                    return "duplicate", "200 duplicate (already sent)"
                if status == "pending_mapping":
                    return "failed", f"{response.status} pending_mapping: a custom webhook; use a rudderstack-format one"
                return "failed", f"{response.status} {answer_fields(text, token)}: not a Crew webhook answer, check the URL"
        except urllib.error.HTTPError as err:
            if 300 <= err.code < 400:
                return "failed", f"{err.code} redirect refused: use the exact url webhooks_create returned"
            text = err.read().decode("utf-8", "replace").strip()
            if err.code < 500 or attempt == 2:
                return "failed", f"{err.code} {answer_fields(text, token)}"
        except OSError as err:  # URLError, timeouts and dropped connections
            if attempt == 2:
                reason = getattr(err, "reason", None) or err.__class__.__name__
                return "failed", f"unreachable: {reason}"
        time.sleep(2)
    return "failed", "unreachable"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--file", required=True, help="JSON list of RudderStack-shaped calls, or - for stdin")
    parser.add_argument("--run", default="test", help="label in every generated messageId; a new one resends")
    parser.add_argument("--keep-timestamps", action="store_true", help="keep each call's originalTimestamp")
    parser.add_argument("--keep-ids", action="store_true", help="keep each call's own messageId")
    parser.add_argument("--pause", type=float, default=5, help="seconds between the identifies and the rest")
    parser.add_argument("--env", help=f"KEY=VALUE file in {ENV_DIR} with CREW_WEBHOOK_URL and CREW_WEBHOOK_TOKEN")
    parser.add_argument("--check", action="store_true", help="validate and show the first call; send nothing")
    parser.add_argument("--try-event", action="store_true", help="print the preview_tryEvent event list; send nothing")
    args = parser.parse_args()
    if not (math.isfinite(args.pause) and 0 <= args.pause <= 300):
        print("--pause must be between 0 and 300 seconds", file=sys.stderr)
        return 2

    try:
        raw = load(args.file)
    except (OSError, ValueError) as err:
        print(f"{args.file}: {err}", file=sys.stderr)
        return 2
    calls, problems = prepare(raw, args.keep_timestamps, args.keep_ids)
    if problems:
        for line in problems:
            print(line, file=sys.stderr)
        print(f"nothing sent: {len(problems)} problem(s) in {len(raw)} call(s)", file=sys.stderr)
        return 2
    if not calls:
        print("nothing to send: the file has no calls", file=sys.stderr)
        return 2
    if not args.keep_ids:
        for position, call in enumerate(calls):
            call["messageId"] = message_id(call, args.run, position)

    if args.try_event:
        entries = try_event_list(calls)
        if not entries:
            print("no track calls to dry-run", file=sys.stderr)
            return 2
        if len(entries) > TRY_EVENT_MAX:
            print(f"{len(entries)} track calls; preview_tryEvent takes at most {TRY_EVENT_MAX} per call: split the file",
                  file=sys.stderr)
            return 2
        if any(c["type"] == "identify" for c in calls):
            note("identify traits are copied into properties for the dry run; in production they live on the profile")
        print(json.dumps(entries, indent=2))
        return 0
    if args.check:
        first = dict(calls[0])
        if not args.keep_timestamps:
            first["originalTimestamp"] = now_utc()
        print(f"{len(calls)} call(s) ready")
        print(json.dumps(first, indent=2))
        return 0

    try:
        env = {**os.environ, **(read_env(args.env) if args.env else {})}
    except (OSError, ValueError) as err:
        print(str(err), file=sys.stderr)
        return 2
    url, token = env.get("CREW_WEBHOOK_URL"), env.get("CREW_WEBHOOK_TOKEN")
    problem = check_url(url)
    if problem or not token:
        print(problem or "CREW_WEBHOOK_TOKEN is not set (in --env or the environment; never as an argument)",
              file=sys.stderr)
        return 2

    print(f"sending {len(calls)} call(s) to {urllib.parse.urlparse(url).hostname}")
    identifies = [c for c in calls if c["type"] == "identify"]
    rest = [c for c in calls if c["type"] != "identify"]
    counts = {"accepted": 0, "duplicate": 0, "failed": 0}
    for group in (identifies, rest):
        if group is rest and identifies and rest:
            time.sleep(args.pause)  # let each profile land before an Agent decides on its person
        for call in group:
            body = dict(call)
            if not args.keep_timestamps:
                body["originalTimestamp"] = now_utc()
            outcome, status = post(url, token, body)
            counts[outcome] += 1
            print(f"{'FAILED' if outcome == 'failed' else 'ok    '} {status} | {describe(call)}")
    print(f"{counts['accepted']} accepted, {counts['duplicate']} duplicate, {counts['failed']} failed")
    if counts["failed"]:
        return 1
    if not counts["accepted"]:
        print("every call was a duplicate, so nothing new reached Crew: pass a new --run to send them again",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
