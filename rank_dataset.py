"""Download consenting adult research faces and evaluate an image regression baseline."""
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import zipfile

import joblib
import numpy as np
import requests
from PIL import Image, ImageOps
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('GALLERY_DATA', str(ROOT / 'data'))) / 'research'
SOURCE = 'https://figshare.com/articles/dataset/Face_Research_Lab_London_Set/5047666'


def download(file):
    target = DATA / file['name']
    if not target.exists():
        print('Downloading', file['name'], flush=True)
        temp = target.with_suffix(target.suffix + '.part')
        with requests.get(file['download_url'], stream=True, timeout=(10, 60)) as r:
            r.raise_for_status()
            with temp.open('wb') as out:
                for chunk in r.iter_content(65536):
                    out.write(chunk)
        temp.replace(target)
    if target.stat().st_size != file['size']:
        raise ValueError('File size mismatch: ' + file['name'])
    if file.get('computed_md5') and hashlib.md5(target.read_bytes()).hexdigest() != file['computed_md5']:
        raise ValueError('Checksum mismatch: ' + file['name'])
    return target


def features(image):
    # Standardized photography permits a small, reproducible pixel baseline.
    # No demographic labels enter the model.
    image = ImageOps.fit(image.convert('L'), (32, 32))
    return np.asarray(image, dtype=np.float64).ravel() / 255


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / 'images').mkdir(exist_ok=True)
    response = requests.get('https://api.figshare.com/v2/articles/5047666', timeout=30)
    response.raise_for_status()
    article = response.json()
    (DATA / 'source.json').write_text(json.dumps(article, indent=2))
    files = {f['name']: f for f in article['files']}
    info_file = download(files['london_faces_info.csv'])
    ratings_file = download(files['london_faces_ratings.csv'])
    archive = download(files['neutral_front.zip'])
    with info_file.open(newline='') as f:
        info = {r['face_id'].zfill(3): r for r in csv.DictReader(f)
                if r['face_age'].strip() and float(r['face_age']) >= 18}
    with ratings_file.open(newline='') as f:
        # Use only adult raters as well as adult photographed subjects.
        raters = [r for r in csv.DictReader(f) if r['rater_age'] and float(r['rater_age']) >= 18]
    rows, vectors, targets = [], [], []
    with zipfile.ZipFile(archive) as z:
        for member in sorted(z.namelist()):
            if member.startswith('__MACOSX/') or not member.lower().endswith(('.jpg', '.png', '.jpeg')):
                continue
            stem = Path(member).stem
            # Archive names use the participant ID followed by expression/view.
            import re
            match = re.match(r'^(\d{3})', stem)
            if not match or match[1] not in info:
                continue
            ident = match[1]
            if any(r['id'] == ident for r in rows):
                raise ValueError('Multiple images per subject would leak across folds.')
            values = [float(r['X'+ident]) for r in raters if r.get('X'+ident, '').strip() not in ('', 'NA')]
            if not values:
                continue
            with Image.open(io.BytesIO(z.read(member))) as image:
                vectors.append(features(image))
                preview = image.convert('RGB')
                preview.thumbnail((512, 512))
                preview.save(DATA / 'images' / (ident + '.jpg'), quality=90)
            targets.append(float(np.mean(values)))
            rows.append(dict(id=ident, age=int(float(info[ident]['face_age'])), filename=ident+'.jpg',
                             human_mean=targets[-1], rating_count=len(values)))
    if len(rows) < 20:
        raise ValueError('Too few eligible adult images: ' + str(len(rows)))
    X, y = np.array(vectors), np.array(targets)
    model = make_pipeline(StandardScaler(), Ridge(alpha=1000, solver='svd'))
    folds = KFold(n_splits=5, shuffle=True, random_state=42)
    predictions = cross_val_predict(model, X, y, cv=folds)
    baseline = np.empty_like(y)
    for train, test in folds.split(X):
        baseline[test] = y[train].mean()
    for row, score in zip(rows, predictions):
        row['score'] = float(np.clip(score, 1, 7))
    rows.sort(key=lambda r: (-r['score'], r['id']))
    for rank, row in enumerate(rows, 1):
        row['rank'] = rank
    model.fit(X, y)
    joblib.dump(model, DATA / 'model.joblib')
    metrics = dict(mae=float(mean_absolute_error(y, predictions)), r2=float(r2_score(y, predictions)),
                   mean_baseline_mae=float(mean_absolute_error(y, baseline)), subjects=len(rows),
                   adult_raters=len(raters))
    manifest = dict(dataset=article['title'], source=SOURCE, license=article['license'],
                    attribution='DeBruine, Lisa; Jones, Benedict (2017). Face Research Lab London Set. figshare. https://doi.org/10.6084/m9.figshare.5047666',
                    model='Grayscale 32×32 pixels → StandardScaler → Ridge (alpha=1000)',
                    method='Five-fold out-of-fold predictions; one image per participant; seed 42. Scores estimate adult raters’ mean attractiveness on a 1–7 scale. Subjective experimental baseline, not an objective measure.',
                    metrics=metrics, pictures=rows)
    temp = DATA / 'rankings.json.tmp'
    temp.write_text(json.dumps(manifest, indent=2, allow_nan=False))
    temp.replace(DATA / 'rankings.json')
    print(json.dumps(metrics, indent=2), flush=True)
    print('Ready: /dataset', flush=True)


if __name__ == '__main__':
    main()
