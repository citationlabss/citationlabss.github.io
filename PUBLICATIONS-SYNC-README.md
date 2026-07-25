# Publications Sync — Setup Guide

This adds a "Publications" list to each lab section on the homepage,
kept up to date from ORCID.

## One-time setup

1. **Add real ORCID iDs.**
   Open `scripts/team-orcids.json` and replace each `0000-0000-0000-0000`
   placeholder with that person's real ORCID iD (format `XXXX-XXXX-XXXX-XXXX`).
   If someone doesn't have one yet, they can create a free one at
   https://orcid.org — leave the field as-is until they do (it will be
   skipped safely otherwise).

2. **Push this whole folder to your GitHub repo**, including the hidden
   `.github/` folder (some file browsers hide dot-folders — make sure
   your Git client or upload includes it).

3. **Enable Actions** if you haven't already: repo → **Settings** →
   **Actions** → **General** → allow workflows to run.

## Running a sync

1. Go to your repo on GitHub → the **Actions** tab.
2. Click **Sync Publications** in the left sidebar.
3. Click the **Run workflow** button (top right) → **Run workflow**.
4. Wait ~30 seconds, refresh — it will commit an updated
   `data/publications.json` if it found anything new.

It also runs automatically every Monday, so it won't go stale even if
nobody clicks anything.

## Tagging a publication to a lab

ORCID has no concept of your labs (Altmetrics, Retractions, etc.) — that
mapping only exists in your head, so after a sync you tag papers by hand:

1. Open `data/publications.json`, find the paper, copy its `"key"` value
   (this is the DOI, lowercased, or a title-based slug if it has no DOI).
2. Open `data/lab-tags.json` and add a line:
   ```json
   "10.1000/some-doi": ["altmetrics", "trends"]
   ```
   A paper can belong to more than one lab — just list all that apply.
3. Commit the change. The website reads this file directly on page
   load — no rebuild or redeploy step needed.

Valid lab ids (must match the section `id=` in `index.html`):
`altmetrics`, `context`, `inequality`, `trends`, `content`,
`conventional`, `interdisciplinarity`, `evaluation`, `retractions`

## A note on Google Scholar

Scholar has no official public API. Any "sync" from it would mean
scraping the page, which Google actively blocks and which can break
without warning — so it's intentionally not included here. ORCID is
the reliable, official source this is built around. If you want Scholar
data too, the practical options are: (a) manually copy entries into
`data/publications.json` yourself in the same format, or (b) use a paid
scraping API like SerpApi — happy to wire that in later if you decide
you need it.

## Testing locally

Browsers block `fetch()` of local JSON files when you just double-click
`index.html` (the `file://` protocol). To preview the publications
working, either:
- push to GitHub and view the live Pages URL, or
- run a quick local server: `python3 -m http.server` in this folder,
  then open `http://localhost:8000`.
