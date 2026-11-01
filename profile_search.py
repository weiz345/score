"""Find public Instagram/LinkedIn links from bounded web search results."""
import os
import re
from urllib.parse import urlsplit, urljoin

from bs4 import BeautifulSoup
import requests


class SearchNotConfigured(RuntimeError):
    pass


def profile_url(value):
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        host = (parsed.hostname or '').lower()
        parts = [p for p in parsed.path.split('/') if p]
        if host in ('instagram.com', 'www.instagram.com') and len(parts) == 1:
            handle = parts[0]
            reserved = {'p', 'reel', 'reels', 'stories', 'explore', 'accounts', 'direct', 'about', 'developer', 'legal', 'famousbirthdays'}
            if re.fullmatch(r'[A-Za-z0-9._]{1,30}', handle) and handle.lower() not in reserved:
                return 'https://www.instagram.com/' + handle.lower() + '/'
        if (host in ('linkedin.com', 'www.linkedin.com') or re.fullmatch(r'[a-z]{2}\.linkedin\.com', host)) and len(parts) == 2 and parts[0] == 'in':
            if re.fullmatch(r'[A-Za-z0-9_%\-]{1,120}', parts[1]):
                return 'https://www.linkedin.com/in/' + parts[1] + '/'
    except (ValueError, TypeError):
        pass
    return None


def discover(query, fetch_page):
    token = os.environ.get('SERPER_API_KEY')
    if not token:
        raise SearchNotConfigured('Web search needs SERPER_API_KEY configured on the server. Profile URLs can still be imported from the homepage.')
    # Credentials remain server-side. Do not expose arbitrary API error bodies.
    response = requests.post('https://google.serper.dev/search',
                             headers={'X-API-KEY': token}, json={'q': query, 'num': 10},
                             timeout=(5, 20), allow_redirects=False)
    if response.status_code != 200:
        raise RuntimeError(f'Search API returned HTTP {response.status_code}. No automatic retry was made.')
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get('organic', []), list):
        raise ValueError('Search API returned an invalid result format.')
    found, errors, seen = [], [], set()

    def add(url, title, source):
        canonical = profile_url(url)
        if canonical and canonical not in seen and len(found) < 20:
            seen.add(canonical)
            found.append({'profile_url': canonical, 'title': title[:200], 'source_url': source})

    pages_read = 0
    for item in payload.get('organic', [])[:10]:
        if not isinstance(item, dict) or not isinstance(item.get('link'), str):
            continue
        url = item['link']; title = str(item.get('title', 'Public profile'))
        if profile_url(url):
            add(url, title, url)
            continue
        if pages_read >= 5:
            continue
        pages_read += 1
        try:
            body, final = fetch_page(url, 2000000)
            soup = BeautifulSoup(body, 'html.parser')
            heading = soup.find('h1')
            page_title = heading.get_text(' ', strip=True)[:200] if heading else title
            for anchor in soup.select('a[href]'):
                add(urljoin(final, anchor['href']), page_title, final)
        except (ValueError, OSError, requests.RequestException):
            errors.append({'source_url': url, 'error': 'Public page unavailable or blocked; skipped.'})
    return {'query': query, 'provider': 'Serper Google search', 'profiles': found, 'page_errors': errors,
            'pages_read': pages_read, 'note': 'Search matches do not verify identity, age, ethnicity, or account ownership. No scoring performed.'}
