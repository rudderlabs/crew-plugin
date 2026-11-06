#!/usr/bin/env python3
"""Check a Crew agent body for the failures that save fine and break silently.

The server accepts all of these. Each one ends with an agent that decides and
then writes nothing, or writes from instructions nobody can see in the editor:

  - an action whose policy id and availableActions id differ (orphaned
    instructions: the editor shows an empty box, the harness generates nothing)
  - an action with no message instructions (availableActions[].payloadTemplate.prompt)
  - message text written into the legacy actionPolicies[].payloadTemplate string,
    which nothing reads
  - an option not linked to an act, or a linked act with no actions (refused when
    the agent is turned on)
  - follow-up gap longer than the attribution window; a Live body naming a
    channelType instead of a channelId

It also warns about things that pass every check and still go wrong:

  - bound agentToolNames: Shadow and dry runs refuse any tool that doesn't
    classify as a read, and nothing on the Agent page shows it
  - heading or list lines in a signal's promptFragment, an option's
    whenToPrefer or a hard constraint's condition: Decide reads each flattened
    to one line, so the structure runs into the text around it
  - on a channel without fields of its own, or a webhook whose only field is
    message, instructions asking for "plain text" while a field the writer
    treats as HTML (any name but subject, subject_line, preheader, preview_text)
    is in outputFields: the writer's system prompt wins. Slack, HeyReach, Twilio
    and CleverTap fields are plain text, so this never applies to them.
  - on a webhook that names its own fields, instructions asking for HTML tags:
    those fields are plain text, and the writer is told so.
  - requiredOutputFields on a channel other than a webhook, which ignores it.

It names a requiredOutputFields entry missing from outputFields too, which the
server refuses outright, so the fix is obvious before the write.

Usage:
  python3 check_body.py body.json        # a bare body, or an agent_get / draft_get response
  python3 check_body.py - < body.json    # from stdin

Exit code 1 when any ERROR is found, else 0. Standard library only.
"""

import json
import re
import sys

WORDS_CHANNEL_TYPES = {"customerio", "clevertap", "twilio", "braze", "heyreach", "slack"}
WORDS_MEDIA = {"email", "slack", "clevertap", "twilio", "braze", "heyreach"}
THIN_INSTRUCTIONS = 150  # characters; below this the writer falls back to its defaults
# Mirrors the writer's rule for a static outputFields list: these names are plain text, and every
# other name is HTML.
TEXT_FIELD_KEYS = {"subject", "subject_line", "preheader", "preview_text"}
STATIC_FIELD_CHANNELS = {None, "webhook"}  # plain-text and templated channels set each field's format themselves
HTML_TAGS = re.compile(r"<(p|br|ul|ol|li|strong|em|a)\b", re.IGNORECASE)
# A Markdown heading, bullet or numbered line. "**bold**" doesn't match: bold survives flattening.
STRUCTURE_LINE = re.compile(r"^[ \t]*(#{1,6}[ \t]|[-*+][ \t]|\d{1,3}[.)][ \t])", re.MULTILINE)


def unwrap(doc):
    """Accept a bare body or a tool response that wraps one under `body`."""
    if isinstance(doc, dict) and "decisionLogic" not in doc and isinstance(doc.get("body"), dict):
        return doc["body"]
    return doc


def slugify(name):
    parts = [p for p in re.split(r"[^a-z0-9]+", (name or "").lower()) if p]
    return "_".join(parts) or "action"


def policy_ids(policies):
    """Mirror assignActionIds: keep explicit ids, mint slugs for the rest, in order."""
    taken, ids = set(), []
    for p in policies:
        pid = p.get("id")
        if not pid:
            base = slugify(p.get("action"))
            pid, n = base, 2
            while pid in taken:
                pid, n = f"{base}_{n}", n + 1
        taken.add(pid)
        ids.append(pid)
    return ids


def resolved_action_id(action, id_by_name):
    """Mirror resolvedAvailableActionId: a.id ?? id of the policy named a.type ?? a.type."""
    return action.get("id") or id_by_name.get(action.get("type")) or action.get("type")


def fixed_clevertap_campaign(action):
    """Mirror channelTypeNeedsMessageInstructions: a bound CleverTap campaign with no
    authored key gives the box nothing to write, so it needs no instructions."""
    if not action.get("cleverTapCampaignId"):
        return False
    keys = action.get("cleverTapKeys") or []
    return not any((k.get("source") or {}).get("kind") == "authored" for k in keys)


def structure_line(text):
    """The first heading or list line in a field Decide reads on one line, else None."""
    match = STRUCTURE_LINE.search(text) if isinstance(text, str) else None
    if match is None:
        return None
    line = text[match.start():].split("\n", 1)[0].strip()
    return line if len(line) <= 40 else line[:40] + "…"


def check(body):
    errors, warnings = [], []
    dl = body.get("decisionLogic") or {}
    policies = dl.get("actionPolicies") or []
    actions = body.get("availableActions") or []
    ids = policy_ids(policies)
    id_by_name = {}
    for p, pid in zip(policies, ids):
        id_by_name.setdefault(p.get("action"), pid)
    resolved = [resolved_action_id(a, id_by_name) for a in actions]
    live = body.get("launchMode") == "live"

    if not policies:
        errors.append("No actions: decisionLogic.actionPolicies is empty.")

    for i, (p, pid) in enumerate(zip(policies, ids)):
        label = f"action '{p.get('action') or pid}'"
        match = next((a for a, rid in zip(actions, resolved) if rid == pid and a.get("enabled", True)), None)
        channel_type = p.get("channelType")
        medium = (match or {}).get("channel")
        writes_words = (channel_type in WORDS_CHANNEL_TYPES) or (medium in WORDS_MEDIA)
        # Only a channelId names the channel: its type, and so whether it needs words, is unknown here.
        untyped = channel_type is None and medium is None
        data_only_note = ("its channel type is not in the body, so this is fine only if channel "
                          f"'{p.get('channelId')}' is a webhook that sends data") if untyped else \
            "fine only if this webhook sends data"

        if isinstance(p.get("payloadTemplate"), str) and p["payloadTemplate"].strip():
            errors.append(f"{label}: text is in decisionLogic.actionPolicies[{i}].payloadTemplate, a legacy "
                          "field nothing reads. Move it to availableActions[].payloadTemplate.prompt.")

        if match is None:
            # Name the entry the author probably meant, so the fix is obvious.
            meant = next((a for a in actions if a.get("id") in (p.get("action"), slugify(p.get("action")))
                          or a.get("type") == p.get("action")), None)
            if meant is None and i < len(actions) and resolved[i] not in ids:
                meant = actions[i]
            if meant is not None:
                errors.append(f"{label}: ORPHANED. Policy id '{pid}' but its availableActions entry has id "
                              f"'{meant.get('id')}'. The editor shows an empty Message instructions box and the "
                              f"harness generates nothing. Give both the same id.")
            elif writes_words:
                errors.append(f"{label}: no availableActions entry with id '{pid}', so nothing is generated.")
            else:
                warnings.append(f"{label}: no availableActions entry ({data_only_note}).")
            continue

        if match.get("enabled") is False:
            warnings.append(f"{label}: its availableActions entry is disabled.")
        if not match.get("id"):
            warnings.append(f"{label}: its availableActions entry has no id. Set it to '{pid}'; the editor and "
                            "the harness resolve id-less entries differently.")

        pt = match.get("payloadTemplate")
        prompt = pt.get("prompt", "") if isinstance(pt, dict) else ""
        if not prompt.strip():
            if fixed_clevertap_campaign(match):
                pass  # every key resolves from traits, events or fixed values
            elif writes_words:
                errors.append(f"{label}: no message instructions (availableActions[].payloadTemplate.prompt). "
                              "The harness skips content generation for it.")
            else:
                warnings.append(f"{label}: no message instructions ({data_only_note}, not words).")
        else:
            if len(prompt.strip()) < THIN_INSTRUCTIONS:
                warnings.append(f"{label}: message instructions are {len(prompt.strip())} characters; this short, "
                                "the writer falls back to its generic defaults. See act-writing.md.")
            fields = pt.get("outputFields") or []
            if not fields:
                warnings.append(f"{label}: no outputFields; the writer falls back to 'subject' and 'body'.")
            else:
                unnamed = [f for f in fields if f.lower() not in prompt.lower()]
                if unnamed:
                    warnings.append(f"{label}: instructions never mention output field(s) {unnamed}; say what goes in each.")
                # Mirrors Crew's webhook rule: a webhook action that names its own fields gets every
                # one as plain text; only a lone `message` stays HTML.
                webhook_named = "webhook" in (channel_type, medium) and fields != ["message"]
                if webhook_named and HTML_TAGS.search(prompt):
                    warnings.append(f"{label}: instructions ask for HTML tags, but a webhook's named fields "
                                    f"{fields} are plain text and the writer is told 'no HTML'. Ask for line "
                                    "breaks instead, or send HTML through a template channel.")
                # Only channels without a template of their own take formats from the field names.
                static_fields = (channel_type in STATIC_FIELD_CHANNELS and medium in STATIC_FIELD_CHANNELS
                                 and not webhook_named)
                html_fields = [f for f in fields if f.lower() not in TEXT_FIELD_KEYS]
                names_formats = re.search(r"<(p|br|ul|ol|li)>|\bhtml\b", prompt, re.IGNORECASE)
                if static_fields and html_fields and "plain text" in prompt.lower() and not names_formats:
                    warnings.append(f"{label}: instructions say 'plain text', but the writer is told {html_fields} "
                                    "may carry HTML (<strong>, <em>, <br>), and its system prompt wins. Name each "
                                    "field's format instead, e.g. 'body is two <p> paragraphs; headline is plain "
                                    "words, no tags'. See act-writing.md, 'Say each field's format'.")
        # Mirrors the server's payloadTemplate check, which refuses the write.
        required = (pt.get("requiredOutputFields") or []) if isinstance(pt, dict) else []
        if required:
            unlisted = [f for f in required if f not in (pt.get("outputFields") or [])]
            if unlisted:
                errors.append(f"{label}: requiredOutputFields {unlisted} are not in outputFields; "
                              "the server refuses the body.")
            elif not untyped and "webhook" not in (channel_type, medium):
                warnings.append(f"{label}: requiredOutputFields only stops a webhook send; this channel ignores it.")
        if channel_type in {"customerio"} or medium == "email":
            if not (match.get("sender") or {}).get("email"):
                warnings.append(f"{label}: email action with no sender email; Customer.io needs a From address.")

        if live and not p.get("channelId"):
            errors.append(f"{label}: launchMode is live but the policy has no channelId (Live refuses channelType).")
        if "shadow" in p:
            warnings.append(f"{label}: has the retired per-action 'shadow' flag; Shadow is the agent's runtime state now.")

    for a, rid in zip(actions, resolved):
        if rid not in ids:
            warnings.append(f"availableActions entry '{a.get('id') or a.get('type')}' matches no action policy; "
                            "its content is never used.")

    act_ids = [a.get("id") for a in dl.get("acts") or []]
    for o in dl.get("options") or []:
        if o.get("actId") not in act_ids:
            errors.append(f"option '{o.get('name') or o.get('id')}': actId '{o.get('actId')}' names no act; "
                          "turning the agent on will refuse it.")
    # Mirror ensureActs: a policy whose actId is missing or names no act belongs to the first act.
    owner_act_ids = {p.get("actId") if p.get("actId") in act_ids else act_ids[0] for p in policies} if act_ids else set()
    # Only Acts an Option links to must own an action; an unlinked Act is never selectable.
    linked_act_ids = {o.get("actId") for o in dl.get("options") or []}
    for aid in act_ids:
        if aid in linked_act_ids and aid not in owner_act_ids:
            errors.append(f"act '{aid}' owns no action but an option links to it; the body is refused.")

    # Decide reads these three on one line each, so a heading or a list in them is lost.
    one_line_fields = [(f"signal '{s.get('name') or s.get('skillId')}'", "promptFragment", s.get("promptFragment"))
                       for s in body.get("skills") or []]
    one_line_fields += [(f"option '{o.get('name') or o.get('id')}'", "whenToPrefer", o.get("whenToPrefer"))
                        for o in dl.get("options") or []]
    one_line_fields += [(f"hard constraint {i + 1}", "condition", c.get("condition"))
                        for i, c in enumerate(dl.get("hardConstraints") or []) if isinstance(c, dict)]
    for label, field, text in one_line_fields:
        line = structure_line(text)
        if line:
            warnings.append(f"{label}: {field} has a heading or list line ({line!r}). Decide reads it flattened "
                            "to one line, so the structure runs into the text around it. Write sentences, bold at "
                            "most. See oda-design.md, 'Write readings a person would say'.")

    fu = body.get("followUp") or {}
    window = body.get("attributionWindowDays")
    if fu.get("enabled") and window and fu.get("gapDays") and fu["gapDays"] > window:
        errors.append(f"followUp.gapDays {fu['gapDays']} is longer than attributionWindowDays {window}.")

    tools = body.get("agentToolNames") or []
    if tools:
        warnings.append(f"agentToolNames binds {len(tools)} tool(s): {tools}. Shadow and dry runs refuse any that "
                        "don't classify as reads, and the Agent page doesn't show it. Before building, check each "
                        "one's enrichmentReadAllowed in mcp_listTools (false is a warning sign); after the first "
                        "Shadow decision, run analytics_getExecution {decisionId} and look for calls with ok: false. "
                        "See agent-schema.md, 'Tools in Shadow and dry runs'.")

    if not (body.get("brandVoice") or "").strip():
        warnings.append("brandVoice is empty; the writer then has almost no voice guidance. See act-writing.md.")
    if body.get("status") in ("draft", "active", "paused"):
        warnings.append(f"body.status '{body['status']}' is the retired state model; the states are off/shadow/live, set with agent_update.")

    return errors, warnings


def main():
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.strip().split("\n\n")[-2])
        sys.exit(0 if sys.argv[1:] in (["-h"], ["--help"]) else 2)
    source = "stdin" if sys.argv[1] == "-" else sys.argv[1]
    try:
        raw = sys.stdin.read() if sys.argv[1] == "-" else open(sys.argv[1], encoding="utf-8").read()
        body = unwrap(json.loads(raw))
    except (OSError, ValueError) as exc:
        print(f"check_body.py: cannot read a body from {source}: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(body, dict):
        print(f"check_body.py: {source} holds no Agent body (expected a JSON object)", file=sys.stderr)
        sys.exit(2)
    errors, warnings = check(body)
    name = body.get("displayName") or body.get("skillId") or "agent"
    n = len((body.get("decisionLogic") or {}).get("actionPolicies") or [])
    print(f"{name}: {n} action(s), {len(errors)} error(s), {len(warnings)} warning(s)")
    for e in errors:
        print(f"  ERROR  {e}")
    for w in warnings:
        print(f"  WARN   {w}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
