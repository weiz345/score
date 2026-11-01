"""Collect public Instagram-creator biographies and photos into the unranked gallery.

Deterministic discovery and selection; no login, model calls, or scoring requests.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
import hashlib
import io
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('GALLERY_DATA', str(ROOT / 'data')))
DEFAULT_COUNTRIES = 'southkorea,japan,china,taiwan,vietnam,singapore,malaysia,thailand,philippines,indonesia,nepal,hongkong,cambodia,mongolia,india,pakistan,bangladesh,srilanka'
COUNT = re.compile(r'([\d,]+(?:\.\d+)?)\s*(million|[kK])?\s*(?:(?:dedicated|Instagram|TikTok|YouTube)\s+)*(?:followers|subscribers|fans)')


def fetch(url, limit=3000000):
    with urlopen(Request(url, headers={'User-Agent': 'PublicProfileGallery/1.0'}), timeout=15) as response:
        body = response.read(limit + 1)
        if len(body) > limit:
            raise ValueError('Source exceeds download limit')
        return body


def category(country):
    url = f'https://www.famousbirthdays.com/profession/from/instagramstar-{country}.html'
    try:
        soup = BeautifulSoup(fetch(url), 'html.parser')
        return sorted({'https://www.famousbirthdays.com' + a['href']
                       for a in soup.select('a[href^="/people/"]')})
    except (OSError, ValueError) as error:
        return {'url': url, 'error': str(error)}


def counts(text):
    values = []
    for match in COUNT.finditer(text):
        value = float(match[1].replace(',', ''))
        multiplier = 1000000 if match[2] == 'million' else 1000 if (match[2] or '').lower() == 'k' else 1
        values.append(int(value * multiplier))
    return values


def biography(url):
    try:
        soup = BeautifulSoup(fetch(url), 'html.parser')
        name = soup.title.get_text().split(' - ')[0]
        image = soup.find('meta', property='og:image')
        for node in soup(['script', 'style', 'nav', 'footer']):
            node.decompose()
        text = soup.get_text(' ', strip=True)
        about = text.split(' About ', 1)[-1].split(' Popularity ', 1)[0]
        return {'name': name, 'url': url, 'image_url': image.get('content') if image else None,
                'text': text, 'counts': counts(about)}
    except (OSError, ValueError, AttributeError) as error:
        return {'url': url, 'error': str(error)}


def age_info(text, today):
    match = re.search(r'Birthday (\w+ \d+) , (\d{4}) Birth', text)
    if match:
        birth = datetime.strptime(match[1] + ' ' + match[2], '%B %d %Y').date()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        return {'age': age, 'age_min': age, 'age_max': age, 'birthdate': str(birth),
                'age_range': f'{age} years old · as of {today}'}
    match = re.search(r'Birth Year (\d{4})', text)
    if match:
        year = int(match[1]); low, high = today.year - year - 1, today.year - year
        return {'age': None, 'age_min': low, 'age_max': high, 'birth_year': year,
                'age_range': f'{low}–{high} years old · birth year {year}'}
    return {'age': None, 'age_min': None, 'age_max': None, 'age_range': 'Age not documented'}


def candidate(row, today, maximum):
    text = row.get('text', '')
    header = text.split(' About ', 1)[0]
    if 'Instagram Star' not in header:
        return None, 'not_instagram_biography'
    if 'DEATH DATE' in text or re.search(r'\b(?:passed away|died in|deceased)\b', text, re.I):
        return None, 'deceased_or_uncertain_living_status'
    age = age_info(text, today)
    if age['age_min'] is not None and age['age_min'] < 18:
        return None, 'under_18_or_age_range_overlaps_under_18'
    audience = row.get('counts', [])
    if not audience:
        return None, 'no_reported_audience'
    if max(audience) > maximum:
        return None, 'above_reported_audience_cap'
    image = row.get('image_url') or ''
    if not image or 'large-default' in image:
        return None, 'no_actual_profile_picture'
    personal = text.split(' About ', 1)[-1].split(' Family life ', 1)[0]
    male = bool(re.search(r'\b(?:He|His|he|his)\b', personal))
    female = bool(re.search(r'\b(?:She|Her|she|her)\b', personal))
    gender = 'Men' if male and not female else 'Women' if female and not male else 'Not specified'
    birthplace = re.search(r'Birthplace (.+?) (?:Age |#)', header)
    origin = 'Birthplace: ' + birthplace[1].strip() if birthplace else 'Background not documented'
    result = dict(row, **age, gender=gender, source_label=origin, reported_audience=max(audience))
    return result, None


def download(row, output, today):
    ident = row['url'].rsplit('/', 1)[-1].removesuffix('.html')
    target = output / 'images' / (ident + '.jpg')
    raw = fetch(row['image_url'], limit=10000000)
    with Image.open(io.BytesIO(raw)) as original:
        if original.width * original.height > 25000000:
            raise ValueError('Image is too large')
        image = ImageOps.exif_transpose(original).convert('RGB')
        image.thumbnail((800, 800))
        temporary = target.with_suffix('.part')
        image.save(temporary, format='JPEG', quality=92)
        temporary.replace(target)
        width, height = image.size
    preferred_age = row['age_min'] is not None and 20 <= row['age_min'] <= row['age_max'] <= 30
    return {key: row[key] for key in ('name', 'age', 'age_min', 'age_max', 'age_range', 'gender', 'source_label', 'reported_audience')} | {
        'id': ident, 'participant': row['name'], 'filename': target.name, 'width': width, 'height': height,
        'age_as_of': str(today), 'birthdate': row.get('birthdate'), 'age_source': row['url'],
        'biography_source': row['url'], 'background_source': row['url'],
        'label_basis': 'Public biography birthplace; does not establish ethnicity',
        'gender_basis': 'Public biography language; not inferred from photograph',
        'platform': 'Instagram', 'audience_note': 'Maximum follower/subscriber figure reported by the source biography; may include another platform. Current counts not verified.',
        'audience_display': f"Source reports {row['reported_audience']:,}+ followers/subscribers · current count unverified",
        'profile_url': '', 'image_url': row['image_url'], 'image_base': '/dataset-images/small-creators/',
        'display_group': 'creators', 'photo_date': None, 'adult_at_capture_verified': False,
        'preferred_age_match': preferred_age,
        'demographic_status': 'Preferred age range documented; ethnicity unverified' if preferred_age else 'Age preference not confirmed; ethnicity unverified',
        'image_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=60, help='Maximum NEW profiles to add')
    parser.add_argument('--max-followers', type=int, default=500000)
    parser.add_argument('--workers', type=int, default=6)
    parser.add_argument('--countries', default=DEFAULT_COUNTRIES)
    parser.add_argument('--seed-cache', action='append', default=[], help='Existing public biography JSON records')
    parser.add_argument('--cached-only', action='store_true', help='Reuse source cache without requesting source pages')
    args = parser.parse_args()
    if not 1 <= args.limit <= 300 or not 1 <= args.workers <= 8 or args.max_followers < 1:
        parser.error('Use limit 1–300, workers 1–8 and a positive audience cap')
    today = date.today()
    output = DATA / 'small-creators'; (output / 'images').mkdir(parents=True, exist_ok=True)
    cache_path = output / 'biography-cache.json'
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for filename in args.seed_cache:
        for row in json.loads(Path(filename).read_text()):
            if 'error' not in row:
                cache[row['url']] = row
    report = {'collected_date': str(today), 'source_errors': [], 'excluded': {}, 'download_errors': [], 'added_ids': []}
    if not args.cached_only:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            categories = list(pool.map(category, sorted(set(args.countries.split(',')))))
        urls = set()
        for result in categories:
            if isinstance(result, dict): report['source_errors'].append(result)
            else: urls.update(result)
        missing = sorted(urls - cache.keys())
        print(f'{len(urls)} source profiles discovered; {len(missing)} uncached biographies', flush=True)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            for row in pool.map(biography, missing):
                if 'error' in row: report['source_errors'].append(row)
                else: cache[row['url']] = row
    cache_path.write_text(json.dumps(cache, indent=2))
    manifest_path = output / 'rankings.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'pictures': []}
    existing = {row['id'] for row in manifest['pictures']}
    candidates = []
    for source in cache.values():
        ident = source['url'].rsplit('/', 1)[-1].removesuffix('.html')
        if ident in existing: continue
        row, reason = candidate(source, today, args.max_followers)
        if row: candidates.append(row)
        else: report['excluded'][reason] = report['excluded'].get(reason, 0) + 1
    candidates.sort(key=lambda r: (r['reported_audience'], r['url']))
    added = []
    # Download bounded batches, preserving deterministic selection order.
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        offset = 0
        while len(added) < args.limit and offset < len(candidates):
            batch = candidates[offset:offset + min(args.workers, args.limit-len(added))]
            futures = [(row, pool.submit(download, row, output, today)) for row in batch]
            offset += len(batch)
            for row, future in futures:
                try:
                    result = future.result(); added.append(result); report['added_ids'].append(result['id'])
                except (OSError, ValueError) as error:
                    report['download_errors'].append({'url': row['url'], 'error': str(error)})
    manifest['pictures'].extend(added)
    manifest['pictures'].sort(key=lambda r: r['name'].casefold())
    manifest.update(dataset='Public Instagram profiles · unranked', unranked=True, model='Not scored', metrics=None,
                    source='https://www.famousbirthdays.com/', license={'name': 'Public-source images; reuse rights unverified'},
                    attribution='Public biography and photo source URLs retained per profile. Birthplace is not ethnicity.',
                    image_base='/dataset-images/small-creators/',
                    method='Alphabetical photo gallery. No follower minimum; smaller source-reported audiences selected first. Age 20–30 and Asian background are preferences, not required. Documented under-18s are excluded; missing ages/backgrounds are labeled.',
                    evaluation_note='Counts may be outdated or refer to another platform. Birthplace does not establish ethnicity. Photo dates are unknown. No attractiveness scores or ranks are generated.',
                    updated_date=str(today))
    for name, data in [('rankings.json', manifest), ('last-collection-report.json', report)]:
        target = output / name; temp = target.with_suffix('.tmp'); temp.write_text(json.dumps(data, indent=2, allow_nan=False)); temp.replace(target)
    import csv
    fields = list(dict.fromkeys(key for row in manifest['pictures'] for key in row))
    with (output / 'creators.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(manifest['pictures'])
    print(json.dumps({'added': len(added), 'total': len(manifest['pictures']), 'source_errors': len(report['source_errors']),
                      'download_errors': len(report['download_errors']), 'report': str(output / 'last-collection-report.json')}), flush=True)


if __name__ == '__main__':
    main()
