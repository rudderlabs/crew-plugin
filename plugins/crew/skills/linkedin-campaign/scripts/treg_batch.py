"""Run a batch of treg catalog calls at once and save each response.

Usage: treg_batch.py --out raw/signals [--workers 6] < calls.jsonl

Each input line is {"id": "<name>", "endpoint": "<catalog id>", "body": {...}}, sent as a POST with
that JSON body (the LinkedIn jobs index and Serper both take one). Lines can mix endpoints. The
response goes to <out>/<id>.json. An id whose file already exists is not called again, so a rerun
only pays for what failed. Prints one line per call and the total charged.
"""
import argparse
import json
import os
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

CHARGED = re.compile(r"charged \$([\d.]+)")


def run(call, out):
    name = re.sub(r"[^A-Za-z0-9_.-]", "_", str(call["id"]))
    path = os.path.join(out, f"{name}.json")
    if os.path.exists(path):
        return name, "cached", 0.0, ""
    try:
        r = subprocess.run(["treg", "call", call["endpoint"], "--method", "POST", "--data", json.dumps(call["body"])],
                           capture_output=True, text=True, timeout=120)
    except subprocess.TimeoutExpired:
        return name, "ERROR", 0.0, "timed out after 120 s"
    m = CHARGED.search(r.stderr)
    cost = float(m.group(1)) if m else 0.0
    ok = r.returncode == 0
    try:
        json.loads(r.stdout)
    except ValueError:
        ok = False
    if not ok:
        return name, "ERROR", cost, (r.stderr or r.stdout).strip().replace("\n", " ")[:200]
    with open(path, "w") as f:
        f.write(r.stdout)
    return name, "ok", cost, ""


def main():
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--out", required=True)
    p.add_argument("--workers", type=int, default=6)
    a = p.parse_args()
    calls = [json.loads(line) for line in sys.stdin if line.strip()]
    os.makedirs(a.out, exist_ok=True)
    with ThreadPoolExecutor(a.workers) as pool:
        results = list(pool.map(lambda c: run(c, a.out), calls))
    for name, status, cost, err in results:
        print(f"{status:<7} {name:<40} ${cost:.4f} {err}")
    bad = sum(r[1] == "ERROR" for r in results)
    print(f"{len(results)} calls, {bad} failed, charged ${sum(r[2] for r in results):.4f}; responses in {a.out}")


if __name__ == "__main__":
    main()
