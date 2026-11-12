"""Seed leads in Crew so research enrichments can run on them.

Per lead: the RudderStack identify (name, title, company; the profile URL as the HeyReach send
address) to the lead webhook, and one "<profile event>" with the LinkedIn member id to the
custom webhook mapped memberId -> linkedin.member_id, userId -> user_id. Run it while the Agent
is Off; the profile event is not a trigger, so nothing decides.

Usage: seed_profiles.py --env ~/crew-lists/webhooks/<lead webhookId>.env \
           --custom-env ~/crew-lists/webhooks/<custom webhookId>.env \
           --leads leads.csv --member-ids member_ids.csv \
           --event "ABC Campaign Lead" --profile-event "ABC Lead Profile"

Each --env file is that webhook's own file: CREW_WEBHOOK_URL and CREW_WEBHOOK_TOKEN, in
~/crew-lists/webhooks/ and readable only by you. Reuses the send-list skill's send_leads.py, so
the userId and identify match what its later passes send: by default from that skill installed
next to this one (same parent folder), else pass --send-leads.
"""
import argparse
import csv
import importlib.util
import os
import re
import sys

# <skills>/linkedin-campaign/scripts/ -> <skills>/send-list/scripts/send_leads.py
SEND_LEADS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                          "send-list", "scripts", "send_leads.py")


def target(sl, path):
    """(url, token) from a webhook's file, or exit naming what is wrong with it."""
    try:
        env = sl.read_env(path)
    except (OSError, ValueError) as err:
        sys.exit(str(err))
    url, token = env.get("CREW_WEBHOOK_URL"), env.get("CREW_WEBHOOK_TOKEN")
    if not url or not token:
        sys.exit(f"{path} must set CREW_WEBHOOK_URL and CREW_WEBHOOK_TOKEN")
    if not sl.destination(url):
        sys.exit(f"the URL in {path} must be https (plain http only to this machine)")
    return url, token


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--env", required=True, help="the lead webhook's file in ~/crew-lists/webhooks/")
    p.add_argument("--custom-env", required=True, help="the custom webhook's file in ~/crew-lists/webhooks/")
    p.add_argument("--leads", required=True)
    p.add_argument("--member-ids", required=True)
    p.add_argument("--event", required=True, help="the Agent's lead event (only names the message ids)")
    p.add_argument("--profile-event", required=True, help="a non-trigger event name, e.g. '<Launch> Lead Profile'")
    p.add_argument("--identifier", default="linkedin_url", help="the HeyReach channel's profile_url_identifier")
    p.add_argument("--send-leads", default=SEND_LEADS)
    a = p.parse_args()

    if not os.path.isfile(a.send_leads):
        sys.exit(f"send_leads.py not found at {a.send_leads}: install send-list next to "
                 "this skill or pass --send-leads")
    sys.dont_write_bytecode = True  # send_leads.py may live in a repo; leave no __pycache__ there
    spec = importlib.util.spec_from_file_location("send_leads", a.send_leads)
    sl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sl)

    def profile_slug(url):
        """The same key send_leads.py builds its URLs from, so uk./no-www/query forms still match."""
        m = sl.PROFILE.match((url or "").strip())
        return m.group(1).lower() if m else None

    targets = (("identify",) + target(sl, a.env), ("profile",) + target(sl, a.custom_env))
    for name, url, _ in targets:
        print(f"{name}: sending to {sl.destination(url)}")
    with open(a.member_ids, newline="") as f:
        member = {profile_slug(r["linkedin_url"]): r["member_id"] for r in csv.DictReader(f)
                  if r.get("member_id") and r.get("status", "CURRENT") == "CURRENT"}
    leads, problems = sl.prepare(*sl.load(a.leads))
    for n, reason in problems:
        print(f"row {n}: skipped, {reason}")
    failed = seeded = 0
    key = re.sub(r"[^a-z0-9]+", "-", a.profile_event.lower()).strip("-")
    for lead in leads:
        slug = profile_slug(lead["url"])
        member_id = member.get(slug)
        if not member_id:
            print(f"{lead['user_id']}: no current member id, skipped")
            continue
        identify, _ = sl.payloads(lead, a.event, a.identifier, "seed")
        profile = {"event": a.profile_event, "messageId": f"{key}-{slug}", "userId": lead["user_id"], "memberId": member_id}
        before = failed
        for (name, url, token), body in zip(targets, (identify, profile)):
            ok, status = sl.post(url, token, body)
            failed += not ok
            print(f"{lead['user_id']}: {name} {status}")
        seeded += failed == before  # both calls landed
    print(f"seeded {seeded} of {len(leads)} leads, {failed} calls failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
