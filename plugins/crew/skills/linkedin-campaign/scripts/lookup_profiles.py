"""Verify each lead's current role and fetch their LinkedIn member id through treg.

Usage: lookup_profiles.py --leads leads.csv --out member_ids.csv [--cache raw/] [--workers 6] [--endpoint ID]

One profile lookup per lead (Fetchin through treg, about $0.0015 each when last run; check the
price with catalog_get first), run --workers at a time. A response already in --cache/<slug>.json
is reused for free.
Prints one row per lead and writes linkedin_url,member_id,status,current_title,current_company,country.
status is CURRENT, NOT CURRENT (the role at their current company has ended), COMPANY CHANGED
(their current company is not the one in the leads file) or ERROR.
With --leads-out it also writes the CURRENT rows as a leads file (name,linkedin_url,title,company:
the profile's title, the input's company), at most --per-company per company and --limit in all, in
input order (titles matching --prefer first), so a demo can go from search hits to leads.csv with
no picking in between.
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

SLUG = re.compile(r"linkedin\.com/in/([^/?#]+)", re.I)


def fetch(slug, endpoint, cache):
    path = os.path.join(cache, f"{slug}.json") if cache else None
    if path and os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    run = subprocess.run(["treg", "call", endpoint, "--query", f"profileUrlOrUrn={slug}"],
                         capture_output=True, text=True, timeout=120)
    if run.returncode != 0:
        raise RuntimeError((run.stderr or run.stdout).strip()[:200])
    data = json.loads(run.stdout)
    if path:
        os.makedirs(cache, exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f)
    return data


def summarize(data, company):
    """The member id and whether the person still holds the role at the company we think they're at."""
    b = data.get("body", data)
    pos = b.get("currentPosition") or {}
    exps = b.get("experiences") or []
    exp = next((e for e in exps if pos.get("positionUrn") and e.get("positionUrn") == pos.get("positionUrn")), None) \
        or next((e for e in exps if pos.get("companyId") and (e.get("company") or {}).get("companyId") == pos.get("companyId")), None)
    ongoing = bool(exp) and (exp.get("current") is True or "present" in (exp.get("dateRange") or "").lower())
    now_at = pos.get("name") or ""
    if not b.get("memberId"):
        status = "ERROR"
    elif not ongoing:
        status = "NOT CURRENT"
    elif company and company.lower() not in now_at.lower() and now_at.lower() not in company.lower():
        status = "COMPANY CHANGED"
    else:
        status = "CURRENT"
    return {"member_id": str(b.get("memberId") or ""), "status": status,
            "current_title": pos.get("title") or b.get("jobTitle") or "", "current_company": now_at,
            "country": b.get("geoCountryName") or b.get("countryCode") or "",
            "date_range": (exp or {}).get("dateRange", "")}


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--leads", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--cache", help="directory for raw responses; reused on a rerun")
    p.add_argument("--workers", type=int, default=6)
    p.add_argument("--leads-out", help="also write the CURRENT rows here as leads (name,linkedin_url,title,company)")
    p.add_argument("--per-company", type=int, default=2)
    p.add_argument("--limit", type=int, default=12)
    p.add_argument("--prefer", help="regex: pick titles matching it first, e.g. 'platform|engineering'")
    p.add_argument("--endpoint", default="fetchinio.linkedin.user.profile")
    a = p.parse_args()
    with open(a.leads, newline="", encoding="utf-8-sig") as f:
        leads = list(csv.DictReader(f))

    def check(lead):
        m = SLUG.search(lead.get("linkedin_url") or "")
        if not m:
            return lead, None
        try:
            return lead, summarize(fetch(m.group(1), a.endpoint, a.cache), lead.get("company", ""))
        except Exception as err:  # noqa: BLE001 - one bad lookup must not stop the batch
            return lead, {"member_id": "", "status": "ERROR", "current_title": str(err), "current_company": "", "country": "", "date_range": ""}

    rows = []
    with ThreadPoolExecutor(a.workers) as pool:
        for lead, s in pool.map(check, leads):
            if s is None:
                print(f"{lead.get('name')}: no linkedin.com/in/ URL, skipped", file=sys.stderr)
                continue
            rows.append({"name": lead.get("name", ""), "company": lead.get("company", ""), "linkedin_url": lead["linkedin_url"], **{k: s[k] for k in ("member_id", "status", "current_title", "current_company", "country")}})
            print(f"{s['status']:<15} {lead.get('name', ''):<22} {s['current_title'][:45]:<45} {s['current_company']:<20} {s['country']:<14} {s['date_range']}")
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["linkedin_url", "member_id", "status", "current_title", "current_company", "country"], extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    if a.leads_out:
        picked, per = [], {}
        prefer = re.compile(a.prefer, re.I) if a.prefer else None
        for r in sorted(rows, key=lambda r: not (prefer and prefer.search(r["current_title"]))):
            co = r["company"].lower()
            if r["status"] == "CURRENT" and per.get(co, 0) < a.per_company and len(picked) < a.limit:
                per[co] = per.get(co, 0) + 1
                picked.append({"name": r["name"], "linkedin_url": r["linkedin_url"], "title": r["current_title"], "company": r["company"]})
        with open(a.leads_out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["name", "linkedin_url", "title", "company"])
            w.writeheader()
            w.writerows(picked)
        print(f"wrote {len(picked)} leads to {a.leads_out}")
    bad = sum(r["status"] != "CURRENT" for r in rows)
    print(f"{len(rows)} looked up, {bad} to drop or fix; wrote {a.out}")


if __name__ == "__main__":
    main()
