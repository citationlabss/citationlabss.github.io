# Publications System — How It Works

This site pulls in publications automatically from ORCID, and also lets
you add or edit entries by hand. This document explains the whole
process from scratch.

## The files involved

```
scripts/
  ├── orcid.json          <- the ORCID iD publications are fetched from
  └── fetch_orcid.py       <- the script that does the fetching
data/
  ├── publications.json    <- every publication that appears on the site
  └── lab-tags.json        <- which lab section(s) each publication belongs to
.github/workflows/
  └── sync-publications.yml <- runs the fetch script, on demand or on a schedule
```

`data/publications.json` is the single source of truth for what shows
up on the site. `index.html` reads it directly. Nothing else needs to
be touched for a publication to appear — once it's in that file and
tagged in `lab-tags.json`, it's live.

## How a publication gets into the system

There are two ways:

**1. Automatically, from ORCID.**
`scripts/orcid.json` holds one ORCID iD. Whenever the sync runs, it
looks up that profile's works and adds any it hasn't seen before to
`data/publications.json`.

**2. By hand.**
Open `data/publications.json` and add an entry directly — useful for
talks, book chapters, older work not on ORCID, or anything you'd
rather not wait on a sync for.

Either way, once it's in the file, it works exactly the same going
forward — the site doesn't distinguish between the two.

## Running a sync

1. Go to the repo on GitHub → **Actions** tab.
2. Click **Sync Publications** in the left sidebar.
3. Click **Run workflow** → confirm.
4. Wait about 15–30 seconds, then refresh. If ORCID had anything new,
   you'll see a fresh commit updating `data/publications.json`.

It also runs automatically every Monday, so new papers show up even if
nobody remembers to click anything.

## Editing a publication's details

Open `data/publications.json`, find the entry, and change whatever
field needs fixing — title, authors, year, venue, DOI, or URL.

Once an entry exists in this file, the sync will never touch it again.
It only ever adds publications it hasn't seen before; it never
rewrites, refreshes, or reverts anything already there. So an edit you
make — whether to a hand-added entry or one that originally came from
ORCID — is permanent and safe through every future sync.

(If you ever do want a specific entry to be re-fetched fresh from
ORCID — say, its record there was corrected — delete that entry from
`data/publications.json` and run the sync again. It'll come back in as
new.)

## Adding a publication by hand — the format

Add an object to the `"publications"` array in `data/publications.json`:

```json
{
  "key": "10.xxxx/your-doi-here",
  "title": "The paper's title",
  "authors": ["Author One", "Author Two"],
  "year": "2026",
  "venue": "Journal or Conference Name",
  "doi": "10.xxxx/your-doi-here",
  "url": "https://doi.org/10.xxxx/your-doi-here"
}
```

- `"key"` must be **unique** across the whole file. Use the DOI,
  lowercased, if the publication has one. If it doesn't, use
  `lowercase-title-with-hyphens::year` instead — look at any existing
  entry with `"doi": null` to see the exact pattern.
- Any field can be `null` if you don't have that information (e.g. a
  talk with no DOI).

## Tagging a publication to a lab

A publication won't appear anywhere on the site until it's tagged to
at least one lab.

1. Copy the publication's `"key"` from `data/publications.json`.
2. Open `data/lab-tags.json` and add a line:
   ```json
   "that-key": ["lab-id"]
   ```
3. A publication can belong to more than one lab — just list all that
   apply: `["altmetrics", "trends"]`.
4. Commit the change. The site reads this file directly, so it takes
   effect on next page load — no sync or rebuild needed.

Valid lab ids: `altmetrics`, `context`, `inequality`, `trends`,
`content`, `conventional`, `interdisciplinarity`, `evaluation`,
`retractions`

## Changing which ORCID profile it syncs from

Open `scripts/orcid.json` and replace the `"orcid"` value with a
different ORCID iD, then commit. The next sync will start pulling from
that profile instead.
