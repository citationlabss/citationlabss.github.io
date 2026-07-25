#!/usr/bin/env python3
"""
Suggest lab tags for newly-synced publications, based on keyword matching
against scripts/lab-keywords.json.

Like fetch_orcid.py, this script NEVER writes to data/lab-tags.json - that
file is hand-edited by a human (see its own _readme) and is the single
source of truth for what actually shows up on the site.

Instead, this writes data/suggested-tags.json: a list of publications that
don't have a tag yet in lab-tags.json, along with the lab(s) whose
keywords matched. Review that file, then copy the entries you agree with
into lab-tags.json yourself.

Publications with no keyword match at all are printed to stdout as
"needs a manual look" rather than being silently skipped - many real
papers (workshops, technical notes, etc.) genuinely won't fit any lab,
and that's a judgment call, not something to guess at.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLICATIONS_FILE = ROOT / "data" / "publications.json"
TAGS_FILE = ROOT / "data" / "lab-tags.json"
KEYWORDS_FILE = ROOT / "scripts" / "lab-keywords.json"
SUGGESTIONS_FILE = ROOT / "data" / "suggested-tags.json"


def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text())


def main():
    pubs_data = load_json(PUBLICATIONS_FILE, {"publications": []})
    publications = pubs_data.get("publications", [])

    tags = load_json(TAGS_FILE, {})
    tagged_keys = {k for k in tags.keys() if not k.startswith("_")}

    raw_keywords = load_json(KEYWORDS_FILE, {})
    keywords = {k: v for k, v in raw_keywords.items() if not k.startswith("_")}
    if not keywords:
        print("No keyword rules found in scripts/lab-keywords.json - nothing to do.", file=sys.stderr)
        sys.exit(0)

    suggestions = {}
    unmatched = []

    for pub in publications:
        key = pub.get("key")
        if not key or key in tagged_keys:
            continue

        haystack = f"{pub.get('title') or ''} {pub.get('venue') or ''}".lower()

        matched_labs = []
        for lab_id, terms in keywords.items():
            for term in terms:
                if term.lower() in haystack:
                    matched_labs.append(lab_id)
                    break

        if matched_labs:
            suggestions[key] = sorted(set(matched_labs))
        else:
            unmatched.append(key)

    SUGGESTIONS_FILE.write_text(json.dumps({
        "_readme": [
            "Auto-generated suggestions only - nothing here is applied to the site.",
            "Review each entry below, then copy the ones you agree with into",
            "lab-tags.json by hand (same format: \"key\": [\"lab-id\", ...]).",
            "This file is fully regenerated on every sync run, so there's no",
            "need to clean it up - just leave actioned entries alone, they'll",
            "keep reappearing until the key is added to lab-tags.json."
        ],
        "suggestions": suggestions,
    }, indent=2))

    print(f"Suggested tags for {len(suggestions)} publication(s) -> {SUGGESTIONS_FILE}")
    if unmatched:
        print(f"\n{len(unmatched)} publication(s) had no keyword match and need a manual look:")
        for key in unmatched:
            print(f"  - {key}")


if __name__ == "__main__":
    main()
