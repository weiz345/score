# Profile gallery

## Consolidated workspace

This checkout contains the app, discovery experiments, scoring scripts and
local results from the session. Its existing Git remote is
`https://github.com/weiz345/score.git`. No commit or push has been made.

| Location | Contents | Included in Git |
| --- | --- | --- |
| Repository root and `templates/` | Flask app, collectors, scoring integration and UI | Yes |
| `research/` | Discovery, extraction, scoring, location filtering and checks | Scripts and README only |
| `static/` | Generated name searches, picture galleries and score exports | README only |
| `data/` | Photos, SQLite database, manifests, cached scores and models | No |
| `.env.local` | Local API credentials | No |
| `data/logs/web.log` | Local app log | No |

The old `/tmp/creator-research` location is a compatibility symlink into
`research/`. Everything it contained is preserved in this checkout. See
[research/README.md](research/README.md) for the batch workflow and rerun order.

To start a fresh checkout:

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env.local
# Set API keys in .env.local using your editor.
python3 run_local.py
```

For this existing checkout, `.env.local` already contains the Serper setting;
do not overwrite it with the example. Add `ATTRACTIVENESS_API_TOKEN` there if
you need to run scoring later. The server binds to `0.0.0.0:8080`; open the
host's reachable IP address on port 8080. `data/` and generated `static/` files
are local artifacts, so a new clone starts without the saved collections.
Credentials are not included in the repository or Docker image.

The Docker image includes the application and research scripts, without
local datasets or generated results. Mount `data/` at `/data` and, if using
batch-generated views, mount `static/` at `/app/static` as writable directories.
Inject API keys through the container environment. Research batch scripts
reflect this local workflow; review their dataset paths before running them
inside a container with a custom `GALLERY_DATA` mount.

Before committing, inspect `git status` and `git diff`. The current ignore
rules keep credentials, downloaded portraits, research-only datasets, cached
scores and generated profile exports out of `git add .`.


Run `python3 -m pip install -r requirements.txt`, then `python3 app.py`. Open http://127.0.0.1:8080.

Enter one LinkedIn or Instagram profile URL per line. Optionally supply `profile_url,image_url` from an authorized source. The app downloads public Open Graph/Twitter images; these may be generic previews and should be verified. Platforms may block requests or require login; the app reports errors without bypassing restrictions. No real profiles are preloaded.

Pictures persist as JPEGs under `data/images`, with profile URLs and resolved image URLs in `data/gallery.sqlite3`. Select k (1–100) to display the latest k saved pictures; export all saved URLs as CSV. Batches accept up to 20 profiles.

Docker: `docker build -t profile-gallery .` then `docker run --rm -p 127.0.0.1:8080:8080 -v profile-gallery-data:/data profile-gallery`.

This is a local single-user tool; use images you are authorized to collect. Source image URLs may expire. The development server is intended for local use. `/tmp` can be cleared by the host, so copy this project to durable storage if needed.

## Adult research dataset ranking

Install `python3 -m pip install -r requirements-ranking.txt`, then run `OPENBLAS_NUM_THREADS=1 python3 rank_dataset.py`. Open `/dataset` in the same web app. The script downloads the Face Research Lab London Set from figshare (CC BY 4.0); attribution and source metadata are saved and shown in the UI. Subjects with missing ages or ages below 18 are excluded. Only adult raters contribute to the training targets. Demographic labels are not model inputs.

This is an experimental image regression baseline, not a validated attractiveness model: 32×32 grayscale pixels, standardized within each training fold, and Ridge regression with fixed alpha 1000. Displayed scores are five-fold out-of-fold predictions (one photograph per participant, seed 42), clipped to 1–7. The UI shows human rating means separately, held-out MAE and R², and a training-mean baseline. A final model trained on all eligible subjects is saved as `data/research/model.joblib`; it is not used for the displayed held-out predictions. Scores are subjective and dataset-specific. The research dataset supplies no contact details.

Downloaded archives, original metadata, source license information, previews, model and rankings persist under `data/research`. Downloads verify the source-provided size and MD5 checksum. Rerunning reuses downloads and regenerates rankings. The Dockerfile includes the ranking dependencies and both scripts. Run them against the same `/data` volume as the web app.

## Larger FEI dataset

After training the London baseline, run `OPENBLAS_NUM_THREADS=1 python3 rank_fei.py`. This downloads four FEI archives (about 344 MB) and creates 2,800 preview images and scores under `data/fei`. Open `/dataset?set=fei` to view them. The source describes 200 participants aged 19–40, with 14 photographs per participant. These are 2,800 photographs, not 2,800 different people; ages are documented at dataset level, not individually.

FEI permits research use and prohibits redistribution. Keep the database and previews local for research; do not publish them or include them in a distributable project image. Source terms, archive SHA-256 hashes, citation, and the model hash are recorded locally. FEI has no attractiveness targets here: scores use the weak London-trained model without validation on FEI and are affected by camera pose, cropping and lighting. They are an experimental demonstration, not reliable rankings of people. The UI exposes this limitation and does not invent human ratings or validation results.

## attractivenesstest.com model

`rank_api.py` integrates the official API documented at https://attractivenessai.com/api/documentation . Access requires an issued bearer token; obtain access at https://attractivenessai.com/api and configure `ATTRACTIVENESS_API_TOKEN` locally. Do not paste credentials into chat, source code, or browser code.

Run `python3 rank_api.py --dataset research --limit 20` to send up to 20 adult London dataset preview images to the service. The API consumes 3 credits per successful scoring request. Results are shown at `/dataset?set=service`, ranked by the raw 0–10 score, with adjusted scores separate. Scoring does not overwrite local-model results. Results are cached by dataset, image ID, and SHA-256; reruns reuse successful calls. Requests run serially, wait one second after success, and stop on any HTTP error without automatic retries. Existing cache survives failures; the published manifest updates only when the selected batch completes.

Integration development used mocked responses; subsequent live batches are recorded below. FEI's research/no-redistribution terms require resolving permission for third-party uploads first; the script blocks FEI by default. Only after obtaining that permission, use `--dataset fei --fei-upload-permitted --limit N`. Never imply that scores from the local baseline came from this API. The documentation gives a 0–10 score range (the site's consumer page describes it as 1–10).

## Celebrity comparison

`python3 download_celebrities.py` downloads four openly licensed Commons portraits of Emma Watson, Idris Elba, Keanu Reeves and Zendaya. Photo dates are checked conservatively against known birth years to ensure they were adults when photographed. Raw Commons metadata, attribution, license URLs, photo source links, modification descriptions, and hashes are stored under `data/celebrities`. Previews are resized/JPEG re-encoded and retain their source CC BY-SA license; per-photo credits are displayed in the UI.

With API access configured, run `python3 rank_api.py --dataset celebrities --limit 4 --append` to score these portraits and merge/rerank them with existing service results. Successful API calls have now been run on 20 London adult photos and these four portraits. Cached results avoid duplicate charges. The service gallery offers All / Research / Celebrities filtering. These four selected celebrities are a comparison set, not a representative population sample; scores are per photo and not validated judgments of people.

## Asian adult comparison

`python3 prepare_asian.py` selects 12 research faces without replacement (seed 42) from the 19 age-documented adults in the London dataset with self-reported `east_asian`, `west_asian`, or mixed labels. Labels and basis are retained. It also downloads openly licensed adult portraits of Simu Liu, Michelle Yeoh, Jackie Chan, Priyanka Chopra, Deepika Padukone, and Dev Patel; their documented Chinese/Malaysian Chinese/Hong Kong/Indian backgrounds and biography source links are retained. Birth years and image dates are used only to confirm adult status. Ethnicity is never inferred from pictures. This small dataset is not representative of Asian populations and does not imply performance equivalence across subgroups.

With the API token configured, run `python3 rank_api.py --dataset asian_research --limit 12 --output asian-service`, then `python3 rank_api.py --dataset asian_celebrities --limit 6 --output asian-service --append`. View `/dataset?set=asian-service`. Research scores already cached from the original London batch are reused. Asian comparison results stay separate from the original service gallery; All / Research / Celebrities filtering applies within the selected gallery.

## Public professional collection

`python3 collect_public_batch.py --limit 20 --education-records /path/to/education.json` discovers personal LinkedIn/Instagram links published in EuroPython 2025 speaker biographies, stopping at 20 distinct directory entries (at most 100 source pages inspected). It downloads available public profile-page images only after the source-backed education filter passes. No login, contact, demographic inference, paid scoring or dating-account creation occurs. This is a professional-directory convenience sample, not a verified demographic/age sample or representative random population. A public link does not establish consent for dating-app use.

The manifest at `data/collection/public-professionals.json` retains each directory page, profile URL, platform, downloaded file/source image URL or error. `/collection` shows successes, pending entries, failures, and provenance separately. Public metadata can be generic; a profile-image URL hint is supplied for review, not identity verification. The script refuses to overwrite an existing batch. The local `data/` directory remains ignored by Git.

### Education criterion

`collection_rules.json` sets completed undergraduate years to 2020–2025 inclusive. Records without a documented year, completed status, undergraduate degree level, and HTTPS evidence URL are excluded. Completion year is not verified age. The existing 20-profile historical batch predates this filter and is not retrospectively labeled eligible.

Supply education records from explicit public or voluntarily supplied information, keyed by exact canonical profile URL:

```json
{
  "https://www.linkedin.com/in/example/": {
    "education": [{
      "degree_level": "undergraduate",
      "completion_status": "completed",
      "completion_year": 2023,
      "source_url": "https://www.linkedin.com/in/example/"
    }]
  }
}
```

The script does not obtain hidden education fields or infer completion from current student status or a master's degree. `surname_examples.txt` contains 30 Chinese surname examples with Chinese characters, shown on `/collection` as a linguistic reference; the collector does not use surnames to infer ethnicity. Demographic selection requires voluntarily supplied or self-reported fields. No gender filter is configured or inferred. The collection page distinguishes current education criteria from the earlier unfiltered historical batch.

The default `/collection` view caps the sample at k=20 and excludes records without source-backed passing education evidence. The existing historical batch has zero eligible records and is therefore not shown as a matching sample. `/collection?history=1` exposes that batch separately. A surname reference is not a demographic classifier, and no new demographic/education matches have been claimed or fabricated.

Current selection update: the user subsequently removed the graduation filter and requested general public profiles, independent of conferences, surname, demographics or celebrity status. `education_filter_enabled` is now false. The earlier verified-education view above is historical. The default `/collection` now reads `data/collection/public-discovery.json`, showing current discovery status for both LinkedIn and Instagram. Search attempts yielded challenges/errors/no usable direct profile links; no fresh sample was obtained and no background job is running. Old conference records remain accessible only through `/collection?history=1`. The conference collector is retained for historical reproduction, not used for the requested new sample. Do not describe a shuffled search sample as uniform random sampling of platform users.


## Creator collection

Imported creator images are shown at `/dataset?set=creators`. The local `data/creators/rankings.json` manifest retains source links, age evidence, image hashes and quality notes. Photo dates and reuse rights are unverified.

With `ATTRACTIVENESS_API_TOKEN` configured locally, run `python3 rank_api.py --dataset creators --output creator-service --limit 16`. Results appear at `/dataset?set=creator-service`. This keeps creator results separate and reuses the existing API cache. Successful requests cost 3 credits each (up to 48 for 16 images); the script stops on API errors. No token belongs in source control.


## Smaller creators (unranked)

Open `/dataset?set=small-creators` for the public-profile image collection of men and women aged 20–30, displayed alphabetically with gender filters and source-reported audience counts. There is no minimum follower count. Images and provenance live in `data/small-creators`; no scores or ranks are generated. Public biographies report origin/nationality, not inferred ethnicity. Counts may be outdated, photo dates are unknown, and source image reuse rights are not established. This collection is not registered as an API scoring dataset.


## Repeatable Instagram collection

Run `python3 collect_instagram_batch.py --limit 60 --workers 6` to add up to 60 new public profiles to `/dataset?set=small-creators`. Discovery, cached biography parsing, eligibility checks, image downloads and gallery import run without an AI model or scoring service. Source-country seed pages and a 500,000 source-reported audience cap are configurable; smaller audiences are selected first, with a URL tie-breaker. There is no minimum. Known profiles are deduplicated, source biographies cached, and failures recorded in `data/small-creators/last-collection-report.json`. Use `--cached-only` to avoid refetching source pages. Source age and Asian background are preferences; documented under-18s are excluded and missing information labeled. Counts may be stale or include another platform. Photos and collected personal data remain outside git.


## Find profiles by name or search query

Open `/search` to enter a name or web search query. Configure `SERPER_API_KEY` in the server environment and restart the app to enable Serper Google search. The key stays server-side and is never requested in browser UI. Searches request up to 10 results, inspect at most five public pages, and extract at most 20 Instagram/LinkedIn person-profile links. Login-required or blocked pages are skipped. Public search results may be stale or refer to unrelated people; no demographic labels are inferred.

Select profile links and choose **Import selected pictures** to download public profile metadata images into the homepage gallery. Existing saved profile URLs are reused to avoid repeated downloads. Search/source provenance persists in `data/search`. Imports do not call the scoring API. API/provider credits may be consumed by searches.
