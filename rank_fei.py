"""Download FEI for local research and score images with the London baseline."""
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path

import joblib
import numpy as np
import requests
from PIL import Image
from rank_dataset import features

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('GALLERY_DATA', str(ROOT / 'data')))
SOURCE = 'https://fei.edu.br/~cet/facedatabase.html'


def main():
    out = DATA / 'fei'
    (out / 'images').mkdir(parents=True, exist_ok=True)
    model_path = DATA / 'research' / 'model.joblib'
    if not model_path.exists():
        raise SystemExit('Run rank_dataset.py first to train the baseline model.')
    model = joblib.load(model_path)
    response = requests.get(SOURCE, timeout=30)
    response.raise_for_status()
    (out / 'source.html').write_text(response.text)
    records, provenance = [], []
    for part in range(1, 5):
        name = f'originalimages_part{part}.zip'
        url = 'https://fei.edu.br/~cet/' + name
        archive = out / name
        if not archive.exists():
            print('Downloading', name, flush=True)
            temp = archive.with_suffix('.zip.part')
            with requests.get(url, stream=True, timeout=(10, 90)) as r:
                r.raise_for_status()
                with temp.open('wb') as f:
                    for chunk in r.iter_content(1024*1024):
                        f.write(chunk)
            with zipfile.ZipFile(temp) as z:
                if z.testzip(): raise ValueError('Corrupt archive: '+name)
            temp.replace(archive)
        provenance.append(dict(url=url, sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
        with zipfile.ZipFile(archive) as z:
            for member in sorted(z.namelist()):
                match = re.fullmatch(r'(\d+)-(\d+)\.jpg', Path(member).name, re.I)
                if not match or member.startswith('__MACOSX/'):
                    continue
                subject, pose = map(int, match.groups())
                if not 1 <= subject <= 200 or not 1 <= pose <= 14:
                    raise ValueError('Unexpected participant/pose: '+member)
                filename = f'{subject:03d}-{pose:02d}.jpg'
                with Image.open(io.BytesIO(z.read(member))) as im:
                    score = float(np.clip(model.predict([features(im)])[0], 1, 7))
                    preview = im.convert('RGB')
                    preview.thumbnail((512, 512))
                    preview.save(out / 'images' / filename, quality=90)
                records.append(dict(id=f'{subject:03d}-{pose:02d}', participant=f'{subject:03d}',
                                    pose=pose, filename=filename, score=score, age_range='19–40'))
        print(f'Processed part {part}: {len(records)} photos', flush=True)
    if len(records) != 2800 or len({r['id'] for r in records}) != 2800:
        raise ValueError('Expected 2,800 unique photo IDs.')
    records.sort(key=lambda p: (-p['score'], p['id']))
    for rank, record in enumerate(records, 1):
        record['rank'] = rank
    result = dict(dataset='FEI Face Database', source=SOURCE,
                  license=dict(name='Research use only; no redistribution'),
                  attribution='C. E. Thomaz and G. A. Giraldi (2010). A new ranking method for Principal Components Analysis and its application to face image analysis. Image and Vision Computing 28(6), 902–913.',
                  model='London-trained grayscale 32×32 pixel Ridge baseline',
                  method='Subjective experimental attractiveness estimates on a 1–7 scale. Scores are per photograph, not per person. No FEI attractiveness labels or validation are available; pose, framing, and lighting can dominate scores. The source documents ages 19–40 at dataset level; individual ages are unavailable.',
                  metrics=None, participants=200, archives=provenance,
                  model_sha256=hashlib.sha256(model_path.read_bytes()).hexdigest(),
                  pictures=records)
    temp = out / 'rankings.json.tmp'
    temp.write_text(json.dumps(result, indent=2, allow_nan=False))
    temp.replace(out / 'rankings.json')
    print('Ready: /dataset?set=fei — 2800 photos, 200 adults', flush=True)


if __name__ == '__main__':
    main()
