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

@app.get('/dataset')
def dataset_page(): return render_template('dataset.html')

@app.get('/api/dataset')
def dataset_results():
    name = request.args.get('set', 'research')
    if name not in ('research', 'fei', 'service', 'asian-service'):
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
