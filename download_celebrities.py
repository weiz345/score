"""Build a small, attributed adult-celebrity comparison dataset from Commons."""
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re

from PIL import Image
import requests

DATA = Path(os.environ.get('GALLERY_DATA', str(Path(__file__).resolve().parent / 'data')))
OUTPUT_KEY = 'celebrities'
PORTRAITS = [
    ('Emma Watson', 1990, 'Emma Watson 2013.jpg'),
    ('Idris Elba', 1972, 'Idris Elba A House of Dynamite-21 (cropped).jpg'),
    ('Keanu Reeves', 1964, 'Keanu Reeves at TIFF 2025 02 (Cropped).jpg'),
    ('Zendaya', 1996, 'Zendaya-byPhilipRomano.jpg'),
]


def main():
    out = DATA / OUTPUT_KEY
    (out / 'images').mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers['User-Agent'] = 'ProfileGalleryResearch/1.0 (local research; Python requests)'
    response = session.get('https://commons.wikimedia.org/w/api.php', params={
        'action': 'query', 'format': 'json',
        'titles': '|'.join('File:' + p[2] for p in PORTRAITS),
        'prop': 'imageinfo', 'iiprop': 'url|extmetadata', 'iiurlwidth': 600,
    }, timeout=30)
    response.raise_for_status()
    metadata = response.json()
    (out / 'source.json').write_text(json.dumps(metadata, indent=2))
    pages = {p['title']: p for p in metadata['query']['pages'].values()}
    records = []
    for name, born, title in PORTRAITS:
        info = pages['File:' + title.replace('_', ' ')]['imageinfo'][0]
        m = info['extmetadata']
        license_name = m['LicenseShortName']['value']
        if not license_name.startswith(('CC BY ', 'CC BY-SA ')):
            raise ValueError('Unsupported license: ' + license_name)
        year = int(re.search(r'\b(?:19|20)\d{2}\b', m['DateTimeOriginal']['value'])[0])
        if year - born < 19:
            raise ValueError('Adult status cannot be established conservatively: ' + name)
        filename = name.lower().replace(' ', '-') + '.jpg'
        image_url = info.get('thumburl') or info['url']
        image_response = session.get(image_url, timeout=45)
        image_response.raise_for_status()
        with Image.open(io.BytesIO(image_response.content)) as image:
            preview = image.convert('RGB')
            preview.thumbnail((600, 600))
            preview.save(out / 'images' / filename, quality=92)
        artist = html.unescape(re.sub('<[^>]+>', '', m['Artist']['value']))
        records.append(dict(id='celebrity-' + filename[:-4], filename=filename, name=name,
                            participant=name, age_range=f'adult; photographed {year}',
                            category='Celebrity comparison', artist=artist, license_name=license_name,
                            license_url=m['LicenseUrl']['value'], photo_source=info['descriptionurl'],
                            photo_year=year, image_url=image_url,
                            modifications='Resized and JPEG re-encoded; source may already be cropped',
                            image_sha256=hashlib.sha256((out / 'images' / filename).read_bytes()).hexdigest()))
        print('Downloaded:', name, '·', license_name, flush=True)
    manifest = dict(dataset='Adult celebrity portraits from Wikimedia Commons',
                    source='https://commons.wikimedia.org/', license={'name':'Per-image CC BY / CC BY-SA licenses'},
                    attribution='Per-image photographer, license and source shown on each card.',
                    pictures=records)
    (out / 'rankings.json').write_text(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
