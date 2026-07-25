#!/usr/bin/env python3
"""
Fetch publications for each team member from the public ORCID API and
write a merged, de-duplicated list to ../data/publications.json.

No external dependencies - uses only the Python standard library so it
runs on a plain GitHub Actions runner with no extra pip installs.

This script only READS from ORCID and from data/manual-publications.json
(hand-added entries that ORCID doesn't have). It never writes back to
either of those, and it never touches data/lab-tags.json (that file is
edited by hand to decide which lab each paper belongs to).
"""

import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent.parent
TEAM_FILE = ROOT / "scripts" / "team-orcids.json"
OUTPUT_FILE = ROOT / "data" / "publications.json"
MANUAL_FILE = ROOT / "data" / "manual-publications.json"

API_BASE = "https://pub.orcid.org/v3.0"
HEADERS = {"Accept": "application/json"}

PLACEHOLDER_ORCID = re.compile(r"^0000-0000-0000-0000$")
ORCID_ID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[0-9X]$")


def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"  ! HTTP {e.code} on {url} (attempt {attempt+1}/{retries})", file=sys.stderr)
        except Exception as e:
            print(f"  ! Error on {url}: {e} (attempt {attempt+1}/{retries})", file=sys.stderr)
        time.sleep(2)
    return None


def get_works_summaries(orcid_id):
    """Return list of (put_code, work_summary_dict) for an ORCID iD."""
    data = fetch_json(f"{API_BASE}/{orcid_id}/works")
    if not data:
        return []
    out = []
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        s = summaries[0]  # first source is fine; group = same work from multiple sources
        put_code = s.get("put-code")
        if put_code is not None:
            out.append((put_code, s))
    return out


def get_full_records(orcid_id, put_codes, chunk_size=40):
    """Bulk-fetch full work records (for author/contributor lists)."""
    records = []
    for i in range(0, len(put_codes), chunk_size):
        chunk = put_codes[i:i + chunk_size]
        codes_str = ",".join(str(c) for c in chunk)
        data = fetch_json(f"{API_BASE}/{orcid_id}/works/{codes_str}")
        if not data:
            continue
        for item in data.get("bulk", []):
            work = item.get("work")
            if work:
                records.append(work)
    return records


def extract_doi(external_ids):
    if not external_ids:
        return None, None
    for eid in external_ids.get("external-id", []):
        if (eid.get("external-id-type") or "").lower() == "doi":
            value = eid.get("external-id-value")
            url_block = eid.get("external-id-url") or {}
            url = url_block.get("value")
            return value, url
    return None, None


def extract_any_url(external_ids, work_url_block):
    doi, doi_url = extract_doi(external_ids)
    if doi_url:
        return doi_url
    if work_url_block and work_url_block.get("value"):
        return work_url_block["value"]
    if external_ids:
        for eid in external_ids.get("external-id", []):
            url_block = eid.get("external-id-url") or {}
            if url_block.get("value"):
                return url_block["value"]
    return None


def extract_authors(work):
    contributors = (work.get("contributors") or {}).get("contributor") or []
    names = []
    for c in contributors:
        credit_name = (c.get("credit-name") or {}).get("value")
        if credit_name:
            names.append(credit_name)
    return names


def slugify_key(title, year):
    base = re.sub(r"[^a-z0-9]+", "-", (title or "untitled").lower()).strip("-")
    return f"{base}::{year or 'n.d.'}"


def load_manual_publications():
    """Publications added by hand in data/manual-publications.json.

    These are merged in on top of whatever ORCID returns, and always win
    on a key collision (they were typed in on purpose). This file is
    never written to by this script - only read.
    """
    if not MANUAL_FILE.exists():
        return []
    data = json.loads(MANUAL_FILE.read_text())
    manual = []
    for pub in data.get("publications", []):
        if not isinstance(pub, dict) or not pub.get("key"):
            continue
        if pub["key"].startswith("_example"):
            continue
        manual.append(pub)
    return manual


def main():
    if not TEAM_FILE.exists():
        print(f"Missing {TEAM_FILE}", file=sys.stderr)
        sys.exit(1)

    team = json.loads(TEAM_FILE.read_text())
    team = {k: v for k, v in team.items() if not k.startswith("_")}

    publications = {}  # key -> record

    for name, orcid_id in team.items():
        if not orcid_id or PLACEHOLDER_ORCID.match(orcid_id or ""):
            print(f"- Skipping {name}: no real ORCID iD set yet")
            continue
        if not ORCID_ID_RE.match(orcid_id):
            print(f"- Skipping {name}: '{orcid_id}' doesn't look like a valid ORCID iD")
            continue

        print(f"- Fetching works for {name} ({orcid_id})")
        summaries = get_works_summaries(orcid_id)
        if not summaries:
            print(f"  (no works found or profile is private)")
            continue

        put_codes = [pc for pc, _ in summaries]
        full_records = get_full_records(orcid_id, put_codes)
        full_by_putcode = {r.get("put-code"): r for r in full_records if r.get("put-code") is not None}

        for put_code, summary in summaries:
            title = ((summary.get("title") or {}).get("title") or {}).get("value")
            journal = (summary.get("journal-title") or {}).get("value")
            year = ((summary.get("publication-date") or {}).get("year") or {}).get("value")
            external_ids = summary.get("external-ids")
            doi, _ = extract_doi(external_ids)
            url = extract_any_url(external_ids, summary.get("url"))

            full = full_by_putcode.get(put_code)
            authors = extract_authors(full) if full else []
            if name not in authors:
                authors = authors or [name]

            key = doi.lower() if doi else slugify_key(title, year)

            if key in publications:
                # merge: add this member as a contributing author source if missing
                existing = publications[key]
                if name not in existing["authors"]:
                    existing["authors"].append(name)
            else:
                publications[key] = {
                    "key": key,
                    "title": title or "Untitled",
                    "authors": authors,
                    "year": year,
                    "venue": journal,
                    "doi": doi,
                    "url": url,
                }

    manual_pubs = load_manual_publications()
    for pub in manual_pubs:
        publications[pub["key"]] = pub
    if manual_pubs:
        print(f"- Merged {len(manual_pubs)} manually-added publication(s) from {MANUAL_FILE.name}")

    pub_list = list(publications.values())
    pub_list.sort(key=lambda p: (p.get("year") or "0"), reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publications": pub_list,
    }, indent=2))

    print(f"\nWrote {len(pub_list)} publications to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
