"""Official attractivenesstest.com API integration; requires issued API access."""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import time

import requests

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('GALLERY_DATA', str(ROOT / 'data')))
ENDPOINT = 'https://api.rate-my-photo.com/attractiveness'


def analyze(session, image, token):
    response = session.post(ENDPOINT, headers={
        'Authorization': 'Bearer ' + token, 'X-API-Version': '1.1',
    }, json=dict(face_image=base64.b64encode(image).decode('ascii'),
                 return_gender=False, return_face_base64=False, return_boundary_box=False),
        timeout=(10, 60), allow_redirects=False)
    if response.status_code != 200:
        # Do not log request headers, bearer tokens, or arbitrary response bodies.
        raise RuntimeError(f'API returned HTTP {response.status_code}; stopped without automatic retries.')
    result = response.json()
    for name in ('score', 'score_adjusted'):
        value = result.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 10:
            raise ValueError('API returned an invalid ' + name)
    if result.get('api_version') != '1.1':
        raise ValueError('Unexpected API version')
    return {key: result[key] for key in ('score', 'score_adjusted', 'api_version')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', choices=['research', 'fei', 'celebrities', 'asian_research', 'asian_celebrities', 'creators'], default='research')
    parser.add_argument('--output', choices=['service', 'asian-service', 'creator-service'], default='service')
    parser.add_argument('--append', action='store_true', help='Merge into existing service results and rerank.')
    parser.add_argument('--limit', type=int, default=20, help='Maximum photos; 3 service credits each.')
    parser.add_argument('--fei-upload-permitted', action='store_true',
                        help='Use only after obtaining permission to upload FEI photos to this third party.')
    args = parser.parse_args()
    if not 1 <= args.limit <= 2800:
        parser.error('--limit must be 1–2800')
    if args.dataset == 'fei' and not args.fei_upload_permitted:
        parser.error('FEI prohibits redistribution. Obtain permission for third-party processing first, then use --fei-upload-permitted.')
    if (args.dataset == 'creators') != (args.output == 'creator-service'):
        parser.error('Use --dataset creators with --output creator-service to keep creator results separate.')
    token = os.environ.get('ATTRACTIVENESS_API_TOKEN')
    if not token:
        raise SystemExit('Set ATTRACTIVENESS_API_TOKEN locally using an issued API token. Request access: https://attractivenessai.com/api . No images sent.')
    original = json.loads((DATA / args.dataset / 'rankings.json').read_text())
    out = DATA / args.output
    out.mkdir(exist_ok=True)
    cache_path = DATA / 'service' / 'cache.json'
    cache_path.parent.mkdir(exist_ok=True)
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    # Select IDs, not local-model top scores, for a deterministic independent batch.
    selected = sorted(original['pictures'], key=lambda r: r['id'])[:args.limit]
    records = []
    with requests.Session() as session:
        for index, row in enumerate(selected, 1):
            image = (DATA / args.dataset / 'images' / row['filename']).read_bytes()
            key = row.get('cache_dataset', args.dataset) + ':' + row['id'] + ':' + hashlib.sha256(image).hexdigest()
            if key not in cache:
                cache[key] = analyze(session, image, token)
                temp = cache_path.with_suffix('.tmp')
                temp.write_text(json.dumps(cache, indent=2))
                temp.replace(cache_path)
                time.sleep(1)
            result = cache[key]
            record = dict(row, score=result['score'], score_adjusted=result['score_adjusted'],
                          api_version=result['api_version'], dataset_key=args.dataset,
                          image_base=row.get('image_base', '/dataset-images/' + (args.dataset+'/' if args.dataset != 'research' else '')))
            records.append(record)
            print(f'Processed {index}/{len(selected)}', flush=True)
    existing_path = out / 'rankings.json'
    previous = json.loads(existing_path.read_text()) if args.append and existing_path.exists() else None
    if previous:
        incoming = {(r['dataset_key'], r['id']) for r in records}
        kept = [r for r in previous['pictures'] if (r.get('dataset_key', 'research'), r['id']) not in incoming]
        for r in kept:
            r.setdefault('image_base', previous.get('image_base', '/dataset-images/'))
        records.extend(kept)
    records.sort(key=lambda r: (-r['score'], r['id']))
    for rank, row in enumerate(records, 1):
        row['rank'] = rank
    manifest = dict(original, pictures=records, metrics=None, score_max=10,
                    participants=len({r.get('participant', r['id']) for r in records}),
                    image_base='/dataset-images/' + ('fei/' if args.dataset == 'fei' else ''),
                    model='attractivenesstest.com official API v1.1 · raw model score',
                    method='Subjective service estimates, 0–10 scale. Sorted by raw score; adjusted scores are shown separately. No validation on this dataset.',
                    evaluation_note='This third-party model has not been validated on this local dataset. Scores are subjective estimates.',
                    model_source='https://attractivenesstest.com/api')
    if previous and args.output != 'creator-service':
        manifest['dataset'] = 'Adult research faces + celebrity comparison'
        manifest['attribution'] = previous['attribution'] + ' ' + original['attribution']
        manifest['source'] = previous['source']
        manifest['license'] = {'name': 'London: CC BY 4.0; celebrity portraits: per-image CC BY / CC BY-SA'}
    if args.output == 'asian-service':
        manifest['dataset'] = 'Asian adults · random research sample + celebrity comparison'
        manifest['method'] += ' Research selection uses self-reported east_asian, west_asian and mixed labels; celebrity selection uses documented backgrounds. No ethnicity is inferred from photos. This small sample is not representative of Asian populations.'
    temp = out / 'rankings.json.tmp'
    temp.write_text(json.dumps(manifest, indent=2, allow_nan=False))
    temp.replace(out / 'rankings.json')
    print('Ready: /dataset?set=' + args.output)


if __name__ == '__main__':
    main()
