#!/usr/bin/env python3
"""Check the Agent bodies Claude writes to a Crew workspace through the MCP.

Wired in hooks.json as PostToolUse on agent_create and the draft writes; reads
one hook event as JSON on stdin. Runs the workspace-setup skill's check_body.py
over the body just saved and hands its findings to Claude as context. It never
blocks: a draft may be half-built, and check_body.py can lag the newest body
shapes.

Nothing here guards the runtime state: the server creates every MCP-made Agent
Off, turns it on in Shadow, and never takes one Live over MCP.

A failure inside this check lets the call through and says why on stderr.
Standard library only.
"""

import json
import os
import sys

SKILL_SCRIPTS = ("skills", "workspace-setup", "scripts")


def body_of(event):
    body = (event.get("tool_input") or {}).get("body")
    return body if isinstance(body, dict) else None


def report_checks(event):
    body = body_of(event)
    if body is None:
        return
    root = os.environ.get("CLAUDE_PLUGIN_ROOT") or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.dont_write_bytecode = True  # keep __pycache__ out of the plugin folder
    sys.path.insert(0, os.path.join(root, *SKILL_SCRIPTS))
    import check_body  # noqa: E402 -- found through the path set just above

    errors, warnings = check_body.check(check_body.unwrap(body))
    if not errors and not warnings:
        return
    lines = [
        f"crew plugin: check_body.py on the body just saved found {len(errors)} error(s) and "
        f"{len(warnings)} warning(s). Fix the errors before the Agent is turned on; the "
        "workspace-setup skill explains each one."
    ]
    lines += [f"ERROR {e}" for e in errors]
    lines += [f"WARN {w}" for w in warnings]
    json.dump({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "\n".join(lines)}},
              sys.stdout)
    sys.stdout.write("\n")


def main():
    try:
        event = json.load(sys.stdin)
        if event.get("hook_event_name") == "PostToolUse":
            report_checks(event)
    except Exception as exc:  # the check must never block a write because of its own bug
        print(f"crew plugin hook skipped: {exc}", file=sys.stderr)
    sys.exit(0)


if __name__ == "__main__":
    main()
