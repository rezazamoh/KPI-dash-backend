#!/usr/bin/env python3
"""
Compute reviewer response time (min / mean / max) in Gerrit.

Response time = (timestamp of reviewer's first message on the change)
              - (timestamp when that reviewer was added to the change)
"""

import requests
import json
import statistics
from requests.auth import HTTPBasicAuth
from datetime import datetime
from collections import defaultdict

# ---------- CONFIG ----------
GERRIT_URL   = "https://gerrit.sinacomsys.local"      # your Gerrit base URL
USERNAME     = "r.mohammadi"
HTTP_PASSWD  = "r3z@2004"              # from Gerrit > Settings > HTTP Credentials
QUERY        = "status:merged -age:3d"          # tweak as needed
LIMIT        = 10
# ----------------------------

AUTH = HTTPBasicAuth(USERNAME, HTTP_PASSWD)

def gerrit_get(path):
    url = f"{GERRIT_URL}/a{path}"
    r = requests.get(url, auth=AUTH, headers={"Accept": "application/json"})
    r.raise_for_status()
    # Gerrit prefixes responses with )]}'
    return json.loads(r.text.lstrip(")]}'\n"))

def parse_ts(s):
    # Gerrit timestamps: "2024-05-01 12:34:56.000000000"
    return datetime.strptime(s.split(".")[0], "%Y-%m-%d %H:%M:%S")

def fetch_changes():
    path = (f"/changes/?q={QUERY}"
            f"&o=MESSAGES&o=DETAILED_ACCOUNTS&o=REVIEWER_UPDATES"
            f"&n={LIMIT}")
    return gerrit_get(path)

def compute_latencies(changes):
    # reviewer_email -> list of latency seconds
    latencies = defaultdict(list)

    for ch in changes:
        # 1) Build map: reviewer -> earliest "added" time
        added_at = {}
        for upd in ch.get("reviewer_updates", []):
            if upd.get("state") != "REVIEWER":
                continue
            email = upd["reviewer"].get("email")
            if not email:
                continue
            ts = parse_ts(upd["updated"])
            if email not in added_at or ts < added_at[email]:
                added_at[email] = ts

        # 2) For each reviewer, find their first message after being added
        first_msg = {}
        for msg in ch.get("messages", []):
            author = msg.get("author", {}).get("email")
            if not author or author not in added_at:
                continue
            ts = parse_ts(msg["date"])
            if ts < added_at[author]:
                continue  # message before they were (re)added
            if author not in first_msg or ts < first_msg[author]:
                first_msg[author] = ts

        # 3) Compute delta
        for reviewer, added_ts in added_at.items():
            if reviewer in first_msg:
                delta = (first_msg[reviewer] - added_ts).total_seconds()
                latencies[reviewer].append(delta)

    return latencies

def fmt(seconds):
    h = seconds / 3600
    if h < 24:
        return f"{h:6.2f} h"
    return f"{h/24:6.2f} d"

def main():
    changes = fetch_changes()
    print(f"Fetched {len(changes)} changes\n")
    latencies = compute_latencies(changes)

    print(f"{'Reviewer':<40} {'N':>4} {'Min':>10} {'Mean':>10} {'Max':>10}")
    print("-" * 78)
    rows = []
    for r, lats in latencies.items():
        rows.append((r, len(lats), min(lats), statistics.mean(lats), max(lats)))
    rows.sort(key=lambda x: -x[3])   # sort by mean, slowest first
    for r, n, mn, me, mx in rows:
        print(f"{r:<40} {n:>4} {fmt(mn):>10} {fmt(me):>10} {fmt(mx):>10}")

if __name__ == "__main__":
    main()