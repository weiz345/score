"""Collect up to 20 public profile links published in conference biographies."""
import argparse
from datetime import datetime, timezone
import json
import time
from urllib.parse import urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup
from app import DATA, collect
from collection_filters import education_eligibility, RULES

DIRECTORY = 'https://ep2025.europython.eu/speakers/'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--education-records',
                        help='JSON object keyed by exact profile URL, containing source-backed education lists.')
    args = parser.parse_args()
    if not 1 <= args.limit <= 20:
        parser.error('Batch limit is 1–20 public profiles.')
    education_records = {}
    if args.education_records:
        with open(args.education_records) as f:
            education_records = json.load(f)
    elif RULES.get('education_filter_enabled', True):
        parser.error('--education-records is required when the education filter is enabled.')
    if not isinstance(education_records, dict):
        parser.error('--education-records must contain a JSON object keyed by exact profile URL.')
    output = DATA / 'collection'
    output.mkdir(parents=True, exist_ok=True)
    manifest_path = output / 'public-professionals.json'
    if manifest_path.exists():
        raise SystemExit('A batch already exists; inspect it before running another collection.')
    session = requests.Session()
    session.headers['User-Agent'] = 'ProfileGallery/1.0 (public profile collection)'
    response = session.get(DIRECTORY, timeout=25)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, 'html.parser')
    pages = list(dict.fromkeys(urljoin(DIRECTORY, a['href']) for a in soup.select('a[href]')
                               if '/speaker/' in a['href']))
    profiles = []
    seen = set()
    visited = 0
    for page in pages[:100]:
        if len(profiles) >= args.limit:
            break
        visited += 1
        response = session.get(page, timeout=25)
        if response.status_code != 200:
            continue
        soup = BeautifulSoup(response.content, 'html.parser')
        heading = soup.find('h1')
        name = heading.get_text(' ', strip=True) if heading else page.rsplit('/',1)[-1]
        for a in soup.select('a[href]'):
            parsed = urlsplit(urljoin(page, a['href']))
            host = (parsed.hostname or '').lower()
            parts = [s for s in parsed.path.split('/') if s]
            platform = None
            if host in ('linkedin.com','www.linkedin.com') and len(parts)==2 and parts[0]=='in':
                platform = 'LinkedIn'
            if host in ('instagram.com','www.instagram.com') and len(parts)==1 and parts[0].lower() not in ('europython','p','reel','explore','accounts'):
                platform = 'Instagram'
            if not platform:
                continue
            url = urlunsplit(('https',host,parsed.path.rstrip('/')+'/', '', ''))
            if url in seen:
                continue
            seen.add(url)
            profiles.append(dict(name=name, profile_url=url, platform=platform, directory_url=page))
            print('Found',platform,'profile',len(profiles),flush=True)
            # One profile per person, so the cap counts distinct directory entries.
            break
        time.sleep(.3)
    manifest = dict(title='Public professional profile collection', directory=DIRECTORY,
                    created_at=datetime.now(timezone.utc).isoformat(), source_pages_visited=visited,
                    requested=args.limit, results=profiles,
                    education_rules=RULES,
                    note='Profiles are linked by public conference biographies. No demographic or age labels inferred; no contact or paid scoring performed. Public visibility and image availability do not establish consent to dating-app use.')
    def save():
        temp = manifest_path.with_suffix('.tmp')
        temp.write_text(json.dumps(manifest, indent=2))
        temp.replace(manifest_path)
    save()
    for index, row in enumerate(profiles,1):
        eligibility = education_eligibility(education_records.get(row['profile_url']))
        row['education_filter'] = eligibility
        if not eligibility['eligible']:
            row.update(ok=False, excluded=True, error=eligibility['reason'])
            save()
            print(f'{index}/{len(profiles)} excluded by education filter',flush=True)
            continue
        try:
            picture = collect(row['profile_url'])
            row.update(ok=True, **picture)
            image_url = picture['image_url']
            row['profile_image_hint'] = 'profile-displayphoto' in image_url or '-19/' in image_url
            print(f'{index}/{len(profiles)} downloaded',flush=True)
        except (ValueError, OSError, requests.RequestException) as exc:
            row.update(ok=False, error=str(exc))
            print(f'{index}/{len(profiles)} unavailable',flush=True)
        save()
        time.sleep(1)
    summary = dict(discovered=len(profiles), attempted=sum(not r.get('excluded',False) for r in profiles),
                   excluded=sum(r.get('excluded',False) for r in profiles),
                   downloaded=sum(r.get('ok',False) for r in profiles))
    manifest['summary'] = summary
    save()
    print(json.dumps(summary),flush=True)


if __name__ == '__main__':
    main()
