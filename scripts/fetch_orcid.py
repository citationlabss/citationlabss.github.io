#!/usr/bin/env python3
"""
Fetch publications from ONE ORCID profile (see scripts/orcid.json) and
merge them into data/publications.json.

This is the ONLY script in the sync system. No external dependencies -
pure standard library, so it runs on a plain GitHub Actions runner with
nothing extra to install.

MERGE BEHAVIOUR (this is the whole trick that keeps things simple):
- Every publication ORCID returns is added or refreshed in
  data/publications.json, keyed by its "key" (DOI if it has one,
  otherwise a title+year slug).
- Any entry ALREADY in data/publications.json whose key ORCID did NOT
  return this run is left completely untouched.

That means: publications you type into data/publications.json by hand
survive every sync run forever, automatically, with no separate manual
file and no extra step to remember. Just add an entry with a unique
"key" and it stays - the script will never delete it, only ever add or
refresh entries that come from ORCID.
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
ORCID_FILE = ROOT / "scripts" / "orcid.json"
OUTPUT_FILE = ROOT / "data" / "publications.json"

API_BASE = "https://pub.orcid.org/v3.0"
HEADERS = {"Accept": "application/json"}

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
    data = fetch_json(f"{API_BASE}/{orcid_id}/works")
    if not data:
        return []
    out = []
    for group in data.get("group", []):
        summaries = group.get("work-summary", [])
        if not summaries:
            continue
        s = summaries[0]
        put_code = s.get("put-code")
        if put_code is not None:
            out.append((put_code, s))
    return out


def get_full_records(orcid_id, put_codes, chunk_size=40):
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
            return value, url_block.get("value")
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


def load_existing():
    if not OUTPUT_FILE.exists():
        return {}
    data = json.loads(OUTPUT_FILE.read_text())
    return {p["key"]: p for p in data.get("publications", []) if p.get("key")}


def main():
    if not ORCID_FILE.exists():
        print(f"Missing {ORCID_FILE}", file=sys.stderr)
        sys.exit(1)

    config = json.loads(ORCID_FILE.read_text())
    orcid_id = config.get("orcid", "")

    if not ORCID_ID_RE.match(orcid_id or ""):
        print(f"'{orcid_id}' in {ORCID_FILE} doesn't look like a valid ORCID iD - stopping.", file=sys.stderr)
        sys.exit(1)

    existing = load_existing()
    print(f"- {len(existing)} publication(s) already in {OUTPUT_FILE.name} (manual entries kept as-is)")

    print(f"- Fetching works for ORCID {orcid_id}")
    summaries = get_works_summaries(orcid_id)
    if not summaries:
        print("  (no works found, or the profile's works are private)")

    put_codes = [pc for pc, _ in summaries]
    full_records = get_full_records(orcid_id, put_codes)
    full_by_putcode = {r.get("put-code"): r for r in full_records if r.get("put-code") is not None}

    fetched_count = 0
    for put_code, summary in summaries:
        title = ((summary.get("title") or {}).get("title") or {}).get("value")
        journal = (summary.get("journal-title") or {}).get("value")
        year = ((summary.get("publication-date") or {}).get("year") or {}).get("value")
        external_ids = summary.get("external-ids")
        doi, _ = extract_doi(external_ids)
        url = extract_any_url(external_ids, summary.get("url"))

        full = full_by_putcode.get(put_code)
        authors = extract_authors(full) if full else []

        key = doi.lower() if doi else slugify_key(title, year)

        existing[key] = {
            "key": key,
            "title": title or "Untitled",
            "authors": authors,
            "year": year,
            "venue": journal,
            "doi": doi,
            "url": url,
        }
        fetched_count += 1

    pub_list = list(existing.values())
    pub_list.sort(key=lambda p: (p.get("year") or "0"), reverse=True)

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "publications": pub_list,
    }, indent=2))

    print(f"- Refreshed {fetched_count} entr{'y' if fetched_count == 1 else 'ies'} from ORCID")
    print(f"- Wrote {len(pub_list)} publication(s) total to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
