#!/usr/bin/env python3
"""Fail when a customer-facing file names something only RudderStack staff should see.

This repository is public and customers' Claude reads every file in the plugin. The check reads
every file git tracks under plugins/crew/, plus the root README.md and llms.txt, and reports:

  - the private product repository, by its name or path. The marketplace shares the name
    rudder-crew, so the bare word passes; a repository path, or a pull request on it, does not;
  - a host under rudderlabs.com, which is internal, unless PUBLIC_HOSTS lists it;
  - a UUID, which reads as a workspace, Agent or person id from a real run;
  - a pull-request reference such as #1234, PR#12 or owner/repo#1234, of any length, or a link to a
    pull request's page. A bare six- or eight-digit number passes, since it reads as a colour such
    as #122633, and so does any bare number in a .css file or an HTML <style> block, where #333 is
    a colour too.

Run it from the repository root: python3 -I .github/scripts/check_public_text.py
Exit code 1 on any finding, with one GitHub annotation per line found. Standard library only.
"""

import re
import subprocess
import sys

PATHS = ["plugins/crew", "README.md", "llms.txt"]

# Public documentation hosts under rudderlabs.com that a file may link. Empty today: add a host
# here, with the page it serves, before a skill links it.
PUBLIC_HOSTS = set()

HOST = re.compile(r"\b(?:[a-z0-9-]+\.)+rudderlabs\.com\b", re.I)
PR_MESSAGE = "names a pull request; say what changed instead"
RULES = [
    ("names the private product repository; describe the behaviour instead",
     re.compile(r"rudderlabs/rudder-crew\b|rudder-crew[#/]|rudder-claw", re.I)),
    ("names a UUID, which reads as an id from a real workspace; use a <placeholder>",
     re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    # A pull request qualified by its repository (owner/repo#123456) or named as one (PR#12,
    # PR #123456), at any length.
    (PR_MESSAGE,
     re.compile(r"\b[\w.-]+/[\w.-]+#[0-9]+\b|\b(?i:PR)\s*#[0-9]+\b")),
    # A pull request's page, bare or as a Markdown link target.
    ("links a pull request; say what changed instead",
     re.compile(r"github\.com/[\w.-]+/[\w.-]+/pull/[0-9]+", re.I)),
]
# A bare pull request (#1234), at any length but six or eight digits, which read as an all-digit
# colour (#122633). An HTML entity (&#123;), a heading marker (##) and any other word run into a #
# (step#2) are not references. Not applied to CSS, where #333 and #0008 are colours.
BARE_PR = re.compile(r"(?<![A-Za-z0-9&#])#(?:[0-9]{1,5}|[0-9]{7}|[0-9]{9,})\b")


def tracked():
    out = subprocess.run(["git", "ls-files", "-z", "--", *PATHS], check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p]


def findings(path, text):
    css_file = path.lower().endswith(".css")
    html_file = path.lower().endswith((".html", ".htm"))
    in_style = False
    for n, line in enumerate(text.splitlines(), start=1):
        for host in (m.group(0) for m in HOST.finditer(line)):
            if host.lower() not in PUBLIC_HOSTS:
                yield n, f"names the internal host {host}; link a public page instead"
        for message, rule in RULES:
            match = rule.search(line)
            if match:
                yield n, f"{message} ({match.group(0)})"
        css_line = css_file or in_style
        if html_file:
            lower = line.lower()
            opens, closes = lower.rfind("<style"), lower.rfind("</style")
            css_line = css_line or opens != -1
            if opens > closes:
                in_style = True
            elif closes != -1:
                in_style = False
        if not css_line:
            match = BARE_PR.search(line)
            if match:
                yield n, f"{PR_MESSAGE} ({match.group(0)})"


def annotation_property(value):
    """Escape a workflow-command property, so a file name cannot end or extend the command."""
    return (value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            .replace(":", "%3A").replace(",", "%2C"))


def annotation_message(value):
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def main():
    problems = 0
    for path in tracked():
        try:
            with open(path, "rb") as f:
                data = f.read()
        except IsADirectoryError:
            continue
        if b"\0" in data:
            continue  # a binary file: nothing a reader sees as text
        # A stray byte that is not UTF-8 must not hide the rest of the file from the check.
        text = data.decode("utf-8", errors="replace")
        for n, message in findings(path, text):
            problems += 1
            print(f"::error file={annotation_property(path)},line={n}::{annotation_message(message)}")
            print(f"{path}:{n}: {message}", file=sys.stderr)
    if problems:
        print(f"{problems} finding(s) name something private. This repository is public: see "
              "plugins/crew/README.md, \"Adding a skill\".", file=sys.stderr)
        return 1
    print("No private names, internal hosts, ids or PR numbers in the public text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
