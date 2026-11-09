#!/usr/bin/env python3
"""Fail when a customer-facing file names something only RudderStack staff should see.

This repository is public and customers' Claude reads every file in the plugin. The check reads
every file git tracks under plugins/crew/, plus the root README.md and llms.txt, and reports:

  - the private product repository, by its name or path. The marketplace shares the name
    rudder-crew, so the bare word passes; a repository path, or a pull request on it, does not;
  - a host under rudderlabs.com, which is internal, unless PUBLIC_HOSTS lists it;
  - a UUID, which reads as a workspace, Agent or person id from a real run;
  - a pull-request reference such as #1234 or owner/repo#1234. A six-digit colour such as
    #122633 passes.

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
RULES = [
    ("names the private product repository; describe the behaviour instead",
     re.compile(r"rudderlabs/rudder-crew\b|rudder-crew[#/]|rudder-claw", re.I)),
    ("names a UUID, which reads as an id from a real workspace; use a <placeholder>",
     re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)),
    # A bare #1234, or one qualified by its repository (owner/repo#1234). An HTML entity (&#123;),
    # a heading marker (##) and a word run into a # (step#2) are not references.
    ("names a pull request; say what changed instead",
     re.compile(r"(?<![A-Za-z0-9&#])#[0-9]{1,5}\b|\b[\w.-]+/[\w.-]+#[0-9]{1,5}\b")),
]


def tracked():
    out = subprocess.run(["git", "ls-files", "-z", "--", *PATHS], check=True, capture_output=True).stdout
    return [p for p in out.decode().split("\0") if p]


def findings(path, text):
    for n, line in enumerate(text.splitlines(), start=1):
        for host in (m.group(0) for m in HOST.finditer(line)):
            if host.lower() not in PUBLIC_HOSTS:
                yield n, f"names the internal host {host}; link a public page instead"
        for message, rule in RULES:
            match = rule.search(line)
            if match:
                yield n, f"{message} ({match.group(0)})"


def main():
    problems = 0
    for path in tracked():
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except (UnicodeDecodeError, IsADirectoryError):
            continue  # a binary file: nothing a reader sees as text
        for n, message in findings(path, text):
            problems += 1
            print(f"::error file={path},line={n}::{message}")
            print(f"{path}:{n}: {message}", file=sys.stderr)
    if problems:
        print(f"{problems} finding(s) name something private. This repository is public: see "
              "plugins/crew/README.md, \"Adding a skill\".", file=sys.stderr)
        return 1
    print("No private names, internal hosts, ids or PR numbers in the public text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
