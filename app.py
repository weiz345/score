import csv, io, os, socket, ipaddress, sqlite3, uuid, json
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import requests
from PIL import Image
from flask import Flask, request, jsonify, render_template, send_from_directory, Response

ROOT = Path(__file__).resolve().parent
DATA = Path(os.environ.get('GALLERY_DATA', str(ROOT / 'data')))
(DATA / 'images').mkdir(parents=True, exist_ok=True)
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100000

def db():
    con = sqlite3.connect(DATA / 'gallery.sqlite3')
    con.row_factory = sqlite3.Row
    return con

with db() as con:
    con.execute('CREATE TABLE IF NOT EXISTS pictures (id TEXT, profile_url TEXT, image_url TEXT, filename TEXT, width INTEGER, height INTEGER)')

def validate(url):
    p = urlsplit(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Use a public HTTPS URL without credentials or custom ports.')
    if any(not ipaddress.ip_address(a[4][0]).is_global for a in socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)):
        raise ValueError('Private network addresses are not supported.')

def fetch(url, limit):
    with requests.Session() as session:
        session.trust_env = False
        session.headers['User-Agent'] = 'ProfileGallery/1.0'
        for _ in range(5):
            validate(url)
            with session.get(url, timeout=(5, 15), stream=True, allow_redirects=False) as r:
                if r.status_code in (301,302,303,307,308):
                    url = urljoin(url, r.headers.get('Location', ''))
                    continue
                r.raise_for_status()
                body = bytearray()
                for chunk in r.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > limit: raise ValueError('Download exceeds size limit.')
                return bytes(body), url
        raise ValueError('Too many redirects.')

class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.images = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        key = a.get('property', a.get('name', '')).lower()
        if tag == 'meta' and key in ('og:image','twitter:image') and a.get('content'):
            self.images.setdefault(key, a['content'])

def collect(profile, image=''):
    profile, image = profile.strip(), image.strip()
    host = (urlsplit(profile).hostname or '').lower()
    if not any(host == d or host.endswith('.'+d) for d in ('linkedin.com','instagram.com')):
        raise ValueError('Use a LinkedIn or Instagram profile URL.')
    validate(profile)
    if not image:
        body, final = fetch(profile, 2000000)
        parser = Metadata()
        parser.feed(body.decode('utf-8', errors='replace'))
        image = parser.images.get('og:image') or parser.images.get('twitter:image')
        if not image: raise ValueError('No public image metadata. Supply an authorized direct image URL.')
        image = urljoin(final, image)
    body, resolved = fetch(image, 10000000)
    with Image.open(io.BytesIO(body)) as im:
        if im.width * im.height > 25000000: raise ValueError('Image is too large.')
        im.load()
        ident = uuid.uuid4().hex
        filename = ident + '.jpg'
        im.convert('RGB').save(DATA / 'images' / filename, quality=92)
        row = dict(id=ident, profile_url=profile, image_url=resolved, filename=filename, width=im.width, height=im.height)
    with db() as con:
        con.execute('INSERT INTO pictures VALUES (:id,:profile_url,:image_url,:filename,:width,:height)', row)
    return row

@app.get('/')
def index(): return render_template('index.html')

@app.get('/search')
def profile_search_page():
    return render_template('search.html', configured=bool(os.environ.get('SERPER_API_KEY')))

@app.post('/api/profile-search')
def profile_search():
    if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
        return jsonify(error='Cross-origin requests are not allowed'), 403
    payload = request.get_json(silent=True)
    query = payload.get('query') if isinstance(payload, dict) else None
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 200:
        return jsonify(error='Enter a name or search query of 1–200 characters.'), 400
    from profile_search import discover, SearchNotConfigured
    try:
        batch = discover(query.strip(), fetch)
    except SearchNotConfigured as error:
        return jsonify(error=str(error)), 503
    except (ValueError, RuntimeError, requests.RequestException):
        return jsonify(error='The search provider could not complete the request. Check its configuration and quota.'), 502
    batch_id = uuid.uuid4().hex
    directory = DATA / 'search'
    directory.mkdir(exist_ok=True)
    (directory / (batch_id + '.json')).write_text(json.dumps(batch, indent=2))
    return jsonify(batch_id=batch_id, **batch)

@app.post('/api/profile-search/import')
def profile_search_import():
    if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
        return jsonify(error='Cross-origin requests are not allowed'), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify(error='Provide a search batch and selected profile indices.'), 400
    batch_id, indices = payload.get('batch_id'), payload.get('indices')
    if not isinstance(batch_id, str) or len(batch_id) != 32 or any(c not in '0123456789abcdef' for c in batch_id):
        return jsonify(error='Invalid search batch.'), 400
    if not isinstance(indices, list) or not 1 <= len(indices) <= 20 or any(type(i) is not int or i < 0 for i in indices):
        return jsonify(error='Select 1–20 profiles.'), 400
    path = DATA / 'search' / (batch_id + '.json')
    if not path.exists():
        return jsonify(error='Search batch not found. Run the search again.'), 404
    batch = json.loads(path.read_text())
    if any(i >= len(batch['profiles']) for i in indices):
        return jsonify(error='Invalid profile selection.'), 400
    results = []
    for i in dict.fromkeys(indices):
        profile = batch['profiles'][i]['profile_url']
        try:
            with db() as con:
                existing = con.execute('SELECT * FROM pictures WHERE profile_url = ? ORDER BY rowid DESC LIMIT 1', (profile,)).fetchone()
            reused = existing is not None
            picture = dict(existing) if reused else collect(profile)
            result = dict(ok=True, reused=reused, **picture)
        except (ValueError, OSError, requests.RequestException, Image.DecompressionBombError):
            result = dict(ok=False, profile_url=profile, error='Public picture unavailable or blocked; no restrictions were bypassed.')
        result['source_url'] = batch['profiles'][i]['source_url']
        results.append(result)
    batch['imports'] = results
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(batch, indent=2))
    temp.replace(path)
    return jsonify(results=results)

@app.get('/collection')
def collection_page():
    historical_path = DATA / 'collection' / 'public-professionals.json'
    historical = json.loads(historical_path.read_text()) if historical_path.exists() else None
    history = request.args.get('history') == '1'
    path = historical_path if history else DATA / 'collection' / 'public-discovery.json'
    manifest = json.loads(path.read_text()) if path.exists() else None
    rules = json.loads((ROOT / 'collection_rules.json').read_text())
    surnames = [line.strip() for line in (ROOT / 'surname_examples.txt').read_text().splitlines()
                if line.strip() and not line.startswith('#')]
    historical_count = len(historical['results']) if historical else 0
    if manifest and not history and rules.get('education_filter_enabled', False):
        from collection_filters import education_eligibility
        verified = []
        for row in manifest['results']:
            evidence = row.get('education_filter', {})
            result = education_eligibility({'education': [{
                'degree_level': 'undergraduate', 'completion_status': 'completed',
                'completion_year': evidence.get('undergraduate_completion_year'),
                'source_url': evidence.get('education_source'),
            }]})
            if evidence.get('eligible') and result['eligible']:
                verified.append(row)
        manifest = dict(manifest, results=verified[:20], education_rules=rules,
                        summary={'downloaded':sum(bool(r.get('ok')) for r in verified[:20])})
    return render_template('collection.html', batch=manifest, rules=rules, surnames=surnames,
                           history=history, historical_count=historical_count)

@app.get('/dataset')
def dataset_page(): return render_template('dataset.html')

@app.get('/api/dataset')
def dataset_results():
    name = request.args.get('set', 'research')
    if name not in ('research', 'fei', 'service', 'asian-service', 'creators', 'creator-service', 'small-creators'):
        return jsonify(error='Unknown dataset'), 400
    path = DATA / name / 'rankings.json'
    if not path.exists():
        return jsonify(error='Results are not ready. Run rank_api.py for service results, rank_fei.py for FEI, or rank_dataset.py for London.'), 404
    return jsonify(json.loads(path.read_text()))

@app.get('/dataset-images/<filename>')
def dataset_image(filename):
    return send_from_directory(DATA / 'research' / 'images', filename)

@app.get('/dataset-images/fei/<filename>')
def fei_image(filename):
    return send_from_directory(DATA / 'fei' / 'images', filename)

@app.get('/dataset-images/celebrities/<filename>')
def celebrity_image(filename):
    return send_from_directory(DATA / 'celebrities' / 'images', filename)

@app.get('/dataset-images/asian_celebrities/<filename>')
def asian_celebrity_image(filename):
    return send_from_directory(DATA / 'asian_celebrities' / 'images', filename)

@app.get('/dataset-images/creators/<filename>')
def creator_image(filename):
    return send_from_directory(DATA / 'creators' / 'images', filename)

@app.get('/dataset-images/small-creators/<filename>')
def small_creator_image(filename):
    return send_from_directory(DATA / 'small-creators' / 'images', filename)

@app.get('/api/pictures')
def pictures():
    try: k = max(1, min(100, int(request.args.get('k', 12))))
    except ValueError: return jsonify(error='k must be an integer'), 400
    with db() as con:
        rows = [dict(r) for r in con.execute('SELECT * FROM pictures ORDER BY rowid DESC LIMIT ?', (k,))]
        total = con.execute('SELECT count(*) FROM pictures').fetchone()[0]
    return jsonify(pictures=rows, total=total)

@app.post('/api/collect')
def ingest():
    if request.headers.get('Origin') and request.headers['Origin'] != request.host_url.rstrip('/'):
        return jsonify(error='Cross-origin requests are not allowed'), 403
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict) or not isinstance(payload.get('lines'), str):
        return jsonify(error='Provide lines as text'), 400
    lines = [x.strip() for x in payload['lines'].splitlines() if x.strip()]
    if not 1 <= len(lines) <= 20: return jsonify(error='Enter 1–20 profiles per batch'), 400
    results = []
    for line in lines:
        fields = line.split(',', 1)
        try:
            results.append(dict(ok=True, **collect(*fields)))
        except (ValueError, OSError, requests.RequestException, Image.DecompressionBombError) as exc:
            results.append(dict(ok=False, profile_url=fields[0], error=str(exc)))
    return jsonify(results=results)

@app.get('/images/<filename>')
def images(filename): return send_from_directory(DATA / 'images', filename)

@app.get('/export.csv')
def export():
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(['profile_url','image_url','filename','width','height'])
    with db() as con:
        writer.writerows(con.execute('SELECT profile_url,image_url,filename,width,height FROM pictures ORDER BY rowid DESC'))
    return Response(out.getvalue(), mimetype='text/csv', headers={'Content-Disposition':'attachment; filename=profile-pictures.csv'})

if __name__ == '__main__':
    app.run(host=os.environ.get('HOST', '127.0.0.1'), port=int(os.environ.get('PORT', '8080')), threaded=True)
