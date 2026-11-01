# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,csv,io,hashlib,html,re,time
from pathlib import Path
from urllib.parse import urljoin,urlsplit
from concurrent.futures import ThreadPoolExecutor,as_completed
from PIL import Image,ImageStat,ImageOps
from bs4 import BeautifulSoup
sys.path.insert(0,str(_WORKSPACE_ROOT))
from app import fetch,DATA,db
selected={'David Chen','Amy Wang','Eric Zhang','Grace Liu','Jason Li','Angela Huang','Ryan Wu','Jessica Lin','Brian Yang','Tiffany Zhou','Wei Lim','Chloe Tan','Marcus Goh','Rachel Teo','Ethan Lau','Natalie Cheung','Justin Chan','Vivian Lam'}
static=Path(str(_WORKSPACE_ROOT / 'static'));root=DATA/'chinese-name-search';(root/'images').mkdir(parents=True,exist_ok=True)
rows=json.loads((static/'name-search-results.json').read_text())
candidates=[dict(name_seed=r['name'],**p) for r in rows if r['name'] in selected for p in r['profiles'] if p['name_in_search_text']]
def run(row):
 result=dict(row)
 try:
  page,final=fetch(row['profile_url'],2000000)
  soup=BeautifulSoup(page,'html.parser')
  images=[tag.get('content') for key in ['og:image','twitter:image'] for tag in soup.find_all('meta',attrs={'property':key})+soup.find_all('meta',attrs={'name':key}) if tag.get('content')]
  if not images:raise ValueError('No public profile-image metadata')
  image=urljoin(final,images[0])
  if any(s in image.lower() for s in ['ghost-person','default-avatar','default_profile','/rsrc.php','linkedin-logo','company-logo']):raise ValueError('Default or site image excluded')
  body,resolved=fetch(image,10000000)
  with Image.open(io.BytesIO(body)) as im:
   if im.width*im.height>25000000 or min(im.size)<80:raise ValueError('Image too large or too small')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB')
   if max(ImageStat.Stat(im.resize((32,32))).stddev)<5:raise ValueError('Blank image excluded')
   ident=hashlib.sha256(row['profile_url'].encode()).hexdigest()[:24]
   filename=ident+'.jpg';im.save(root/'images'/filename,quality=92)
   result.update(ok=True,id=ident,filename=filename,width=im.width,height=im.height,image_url=resolved,image_sha256=hashlib.sha256(body).hexdigest(),image_path=str(root/'images'/filename))
 except Exception as exc:
  # Store sanitized public failure reason without response bodies.
  result.update(ok=False,error=str(exc)[:180] if isinstance(exc,ValueError) else type(exc).__name__)
 return result
results=[]
with ThreadPoolExecutor(max_workers=6) as pool:
 for i,f in enumerate(as_completed([pool.submit(run,r) for r in candidates]),1):
  results.append(f.result())
  if i%10==0:print(json.dumps({'checked':i,'total':len(candidates),'pictures':sum(r['ok'] for r in results)}),flush=True)
results.sort(key=lambda r:(r['name_seed'],r['profile_url']))
# Repeated identical images across unrelated profiles are not accepted as profile-specific photos.
counts={}
for r in results:
 if r['ok']:counts[r['image_sha256']]=counts.get(r['image_sha256'],0)+1
for r in results:
 if r['ok'] and counts[r['image_sha256']]>1:r.update(ok=False,error='Identical image returned for multiple profiles; excluded')
valid=[r for r in results if r['ok']]
# Import only validated downloadable images into the shared homepage gallery.
with db() as con:
 for r in valid:
  previous=con.execute('SELECT * FROM pictures WHERE profile_url=?',(r['profile_url'],)).fetchone()
  if previous:
   r['gallery_filename']=previous['filename']
  else:
   import shutil
   filename='name-search-'+r['filename'];shutil.copyfile(r['image_path'],DATA/'images'/filename)
   con.execute('INSERT INTO pictures VALUES (?,?,?,?,?,?)',(r['id'],r['profile_url'],r['image_url'],filename,r['width'],r['height']))
   r['gallery_filename']=filename
report={'selection':'Chinese-name search seeds, including English given names with Chinese-family-name spellings. Names do not establish ethnicity.','candidate_count':len(candidates),'verified_image_count':len(valid),'pictures':valid,'excluded':[r for r in results if not r['ok']],'scored':False}
(root/'results.json').write_text(json.dumps(report,indent=2))
(static/'chinese-name-picture-results.json').write_text(json.dumps(report,indent=2))
fields=['name_seed','title','profile_url','image_url','gallery_filename','width','height']
with (static/'chinese-name-picture-results.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(valid)
e=html.escape
parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Chinese-name search: available pictures</title><style>body{font:16px system-ui;max-width:1200px;margin:30px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:18px}article{padding:16px;background:#1c2638;border-radius:12px;overflow-wrap:anywhere}img{width:100%;aspect-ratio:1;object-fit:contain;background:#101522}p{line-height:1.5}</style><a href="/">Profile gallery</a> · <a href="/search">Search</a><h1>Chinese-name search: available pictures</h1>',f'<p>{len(valid)} accounts with successfully downloaded public profile images, from {len(candidates)} candidate links. Names are search seeds, not verified ethnicity. Age, current follower count and identity are unverified. No scores.</p><p><a href="/static/chinese-name-picture-results.csv">Download CSV</a></p><div class="grid">']
for r in valid:
 parts.append('<article><img loading="lazy" alt="Public profile image" src="/images/'+e(r['gallery_filename'],quote=True)+'"><h3>'+e(r['name_seed'])+'</h3><a target="_blank" rel="noopener noreferrer" href="'+e(r['profile_url'],quote=True)+'">'+e(r['title'])+'</a><p>'+e(r['profile_url'])+'</p></article>')
parts.append('</div>')
(static/'chinese-name-picture-results.html').write_text(''.join(parts))
print(json.dumps({'checked':len(results),'pictures':len(valid),'excluded':len(results)-len(valid),'by_platform':{h:sum(h in r['profile_url'] for r in valid) for h in ['instagram.com','linkedin.com']},'errors':{err:sum(r.get('error')==err for r in results) for err in set(r.get('error') for r in results if not r['ok'])}}),flush=True)
