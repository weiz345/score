# Discovery experiments and saved local results

This directory consolidates the earlier `/tmp/creator-research` workspace.
The old path is now a compatibility symlink. Scripts resolve this repository
from their own location instead of assuming a particular container path.

Python scripts and the gallery rendering check are included in Git. Downloaded
photos, raw source pages, search responses, contact sheets, datasets and the
old reference-code snapshot remain local and are ignored. These are experiments
and some are one-time migrations tied to the saved batch, not general commands
for arbitrary datasets. Review a script before rerunning it; searches and
scoring can spend API credits. No scheduled discovery job is installed.

From the repository root, load credentials into the shell before running API
scripts:

```bash
set -a
. ./.env.local
set +a
```

Current batch workflow:

1. `python3 research/seed-name-search.py` generates the name-seed CSV and tries
   three public Google HTML searches; the latter may be unavailable.
2. `python3 research/search-name-batch.py` queries Serper and generates
   `static/name-search-results.html`, JSON and CSV exports.
3. `python3 research/extract-chinese-name-pictures.py` filters the existing
   batch by selected name seeds and extracts public profile images. Names do
   not establish ethnicity. Its results are in `data/chinese-name-search/` and
   `static/chinese-name-picture-results.html`.
4. `python3 research/linkedin-higher-quality.py` checks indexed LinkedIn
   candidates and explicit public cross-links. The one-off
   `save-linkedin-portfolio-upgrade.py` preserves the documented portfolio
   upgrade for Ethan Lau.
5. `python3 research/test-facebook-discovery.py` runs the Facebook batch and
   generates `static/facebook-name-results.html`. These are name matches,
   not verified links to the Instagram accounts.
6. `python3 research/rank-facebook-api.py` scores the manually reviewed
   Facebook subset with three concurrent requests, reusing cached scores.
   It reads `ATTRACTIVENESS_API_TOKEN`, saves each success, and stops starting
   new calls after billing, rate-limit or other service errors. The explicit
   photo selection is specific to this saved batch. Results appear at
   `static/facebook-ranked.html`; excluded-photo reasons are recorded too.
7. `python3 research/filter-north-america.py` annotates this Facebook batch
   using explicit public residence statements and adds location filters.
   Unknown locations remain separate. It uses search credits. Run it after
   regenerating either Facebook page to restore the location controls.

The scoring and location scripts regenerate pages. Rerunning scoring after
the location script requires rerunning the location script for page controls.

Useful checks, with no live API calls:

```bash
python3 research/test-profile-search.py
node research/check-small-ui.js
```

The remaining scripts preserve earlier collection, source review and import
experiments. The token-based Instagram API retry is a live request and is not
an offline test. Keep credentials in the shell environment or ignored
`.env.local`, never in script source.
