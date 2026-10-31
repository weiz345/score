"""Select source-labeled adult research faces and documented celebrity comparisons."""
import csv
import json
from pathlib import Path
import random
import shutil
import requests
import download_celebrities as celebrities

DATA = celebrities.DATA
PEOPLE = [
    ('Simu Liu', 1989, 'Simu Liu by Gage Skidmore 2.jpg', 'Chinese background'),
    ('Michelle Yeoh', 1962, 'Michelle Yeoh-2268.jpg', 'Malaysian Chinese background'),
    ('Jackie Chan', 1954, 'Jackie Chan.jpg', 'Hong Kong Chinese background'),
    ('Priyanka Chopra', 1982, 'Priyanka Chopra at Bulgary launch, 2024 (cropped).jpg', 'Indian background'),
    ('Deepika Padukone', 1986, 'Deepika Padukone 2025 (1).png', 'Indian background'),
    ('Dev Patel', 1990, 'Dev Patel (29870651654).jpg', 'British Indian background'),
]


def main():
    original = json.loads((DATA / 'research' / 'rankings.json').read_text())
    with (DATA / 'research' / 'london_faces_info.csv').open(newline='') as f:
        eligible = {r['face_id']: r for r in csv.DictReader(f)
                    if 'asian' in r['face_eth'] and r['face_age'] and float(r['face_age']) >= 18}
    pool = [r for r in original['pictures'] if r['id'] in eligible]
    chosen = random.Random(42).sample(sorted(pool, key=lambda r:r['id']), min(12, len(pool)))
    out = DATA / 'asian_research'
    (out / 'images').mkdir(parents=True, exist_ok=True)
    rows = []
    for row in chosen:
        shutil.copyfile(DATA / 'research' / 'images' / row['filename'], out / 'images' / row['filename'])
        rows.append(dict(row, source_label=eligible[row['id']]['face_eth'],
                         label_basis='Self-reported dataset label', display_group='research',
                         cache_dataset='research', image_base='/dataset-images/'))
    manifest = dict(original, pictures=rows, selection_seed=42, eligible_count=len(pool),
                    dataset='Random adult Asian-labeled research sample',
                    selection='12 without replacement, seed 42; includes east_asian, west_asian and mixed labels; not a representative sample')
    (out / 'rankings.json').write_text(json.dumps(manifest, indent=2))
    print(f'Selected {len(rows)} random adults from {len(pool)} source-labeled eligible participants.', flush=True)
    celebrities.OUTPUT_KEY = 'asian_celebrities'
    celebrities.PORTRAITS = [r[:3] for r in PEOPLE]
    celebrities.main()
    path = DATA / 'asian_celebrities' / 'rankings.json'
    manifest = json.loads(path.read_text())
    session = requests.Session()
    session.headers['User-Agent'] = 'ProfileGalleryResearch/1.0 (local research; Python requests)'
    biographies = []
    for person in PEOPLE:
        response = session.get('https://en.wikipedia.org/w/api.php', params={
            'action':'query','format':'json','titles':person[0],
            'prop':'extracts','explaintext':1,
        }, timeout=30)
        response.raise_for_status()
        page = next(iter(response.json()['query']['pages'].values()))
        if len(page.get('extract', '')) < 500:
            raise ValueError('Missing biography source: '+person[0])
        biographies.append(page)
    (path.parent / 'biography-sources.json').write_text(json.dumps(biographies, indent=2))
    labels = {r[0]:r[3] for r in PEOPLE}
    for row in manifest['pictures']:
        row.update(source_label=labels[row['name']], label_basis='Documented public biography',
                   biography_source='https://en.wikipedia.org/wiki/'+row['name'].replace(' ','_'),
                   display_group='celebrities')
    path.write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
