# Profile gallery

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
