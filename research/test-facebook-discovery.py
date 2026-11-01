# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,re,io,html,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit,urljoin,parse_qs
import requests
from bs4 import BeautifulSoup
from PIL import Image,ImageOps,ImageStat
sys.path.insert(0,str(_WORKSPACE_ROOT));from app import fetch,DATA
static=Path(str(_WORKSPACE_ROOT / 'static'));root=DATA/'facebook-name-search';root.mkdir(parents=True,exist_ok=True)
rows=json.loads((DATA/'chinese-name-search'/'results.json').read_text())['pictures'];names=sorted(set(p['name_seed'] for p in rows))
key=__import__('os').environ['SERPER_API_KEY']
def profile(url):
 try:
  p=urlsplit(url);parts=[s for s in p.path.split('/') if s]
  if p.scheme!='https' or p.hostname not in ('facebook.com','www.facebook.com','m.facebook.com'):return None
  if len(parts)==1 and parts[0]=='profile.php':
   ident=parse_qs(p.query).get('id',[''])[0]
   return 'https://www.facebook.com/profile.php?id='+ident if ident.isdigit() else None
  if len(parts)==3 and parts[0]=='people' and parts[2].isdigit():return 'https://www.facebook.com/'+ '/'.join(parts)+'/'
  if len(parts)==1 and re.fullmatch('[A-Za-z0-9.]+',parts[0]) and parts[0].lower() not in {'login','share','watch','reels','reel','groups','events','marketplace','help','privacy','photo.php','sharer.php','public','stories','gaming','pages','hashtag'}:return 'https://www.facebook.com/'+parts[0]+'/'
 except ValueError:pass
 return None
def search(name):
 query=f'"{name}" site:facebook.com -inurl:posts -inurl:videos -inurl:reel -inurl:groups'
 row={'name_seed':name,'query':query,'profiles':[],'excluded_nonprofile_results':0}
 try:
  s=requests.Session();s.trust_env=False
  r=s.post('https://google.serper.dev/search',headers={'X-API-KEY':key},json={'q':query,'num':10},timeout=(5,20))
  if r.status_code!=200:row['error']='Search HTTP '+str(r.status_code);return row
  seen=set()
  for item in r.json().get('organic',[])[:10]:
   canonical=profile(item.get('link',''))
   if not canonical:row['excluded_nonprofile_results']+=1;continue
   if canonical in seen:continue
   seen.add(canonical)
   text=(item.get('title','')+' '+item.get('snippet','')).lower()
   if not all(token.lower() in text for token in name.split()):continue
   row['profiles'].append({'name_seed':name,'profile_url':canonical,'title':item.get('title',''),'snippet':item.get('snippet',''),'identity_verified':False})
 except requests.RequestException as e:row['error']=type(e).__name__
 return row
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for i,f in enumerate(as_completed([pool.submit(search,n) for n in names]),1):
  results.append(f.result())
  if i%6==0:print('Searched '+str(i)+'/'+str(len(names))+' names',flush=True)
results.sort(key=lambda r:r['name_seed']);candidates=[];seen=set()
for r in results:
 for p in r['profiles']:
  if p['profile_url'] not in seen:seen.add(p['profile_url']);candidates.append(p)
print('Profile/page candidates: '+str(len(candidates)),flush=True)
def picture(row):
 row=dict(row)
 try:
  body,final=fetch(row['profile_url'],2000000);soup=BeautifulSoup(body,'html.parser')
  tags=soup.select('meta[property="og:image"],meta[name="twitter:image"]')
  images=[t['content'] for t in tags if t.get('content')]
  if not images:raise ValueError('No public profile image metadata')
  image=urljoin(final,images[0])
  if any(s in image.lower() for s in ['/rsrc.php','facebook-logo','silhouette','default_avatar']):raise ValueError('Default or site image excluded')
  raw,resolved=fetch(image,10000000)
  with Image.open(io.BytesIO(raw)) as im:
   if min(im.size)<80 or im.width*im.height>25000000:raise ValueError('Image size excluded')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB')
   if max(ImageStat.Stat(im.resize((32,32))).stddev)<5:raise ValueError('Blank image excluded')
   filename='facebook-'+hashlib.sha256(row['profile_url'].encode()).hexdigest()[:24]+'.jpg';im.save(DATA/'images'/filename,quality=95)
   row.update(picture_available=True,filename=filename,width=im.width,height=im.height,image_url=resolved,image_sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:row.update(picture_available=False,error=str(e)[:160] if isinstance(e,ValueError) else type(e).__name__)
 return row
checked=[]
with ThreadPoolExecutor(max_workers=5) as pool:
 for i,f in enumerate(as_completed([pool.submit(picture,p) for p in candidates]),1):
  checked.append(f.result())
  if i%15==0:print('Checked '+str(i)+'/'+str(len(candidates))+' candidates; '+str(sum(p['picture_available'] for p in checked))+' images',flush=True)
# Generic pictures shared by unrelated profiles do not count.
counts={}
for p in checked:
 if p['picture_available']:counts[p['image_sha256']]=counts.get(p['image_sha256'],0)+1
for p in checked:
 if p['picture_available'] and counts[p['image_sha256']]>1:p.update(picture_available=False,error='Shared generic image excluded')
checked.sort(key=lambda r:(r['name_seed'],r['profile_url']))
report={'name_queries':len(names),'candidate_profiles_or_pages':len(candidates),'downloadable_images':sum(p['picture_available'] for p in checked),'identity_matches_to_instagram_verified':0,'note':'Names are search seeds, not ethnicity or identity evidence. Results may include public pages, businesses, or namesakes. No ranking or scoring.','searches':results,'profiles':checked}
for path in [root/'results.json',static/'facebook-name-results.json']:path.write_text(json.dumps(report,indent=2))
e=html.escape;parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Facebook discovery test</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}article{padding:16px;background:#1c2638;border-radius:12px;overflow-wrap:anywhere}img{width:100%;aspect-ratio:1;object-fit:contain}p{line-height:1.5}summary{cursor:pointer}</style><a href="/static/chinese-name-picture-results.html">Instagram gallery</a> · <a href="/search">Search</a><h1>Facebook discovery test</h1>',f'<p>{len(names)} Chinese-name seeds searched. {len(candidates)} profile/page candidates; {report["downloadable_images"]} downloadable public images. These are name-search hits, not verified matches to Instagram accounts. Names do not verify ethnicity; pages may represent businesses. No scoring.</p><div class="grid">']
for p in checked:
 if not p['picture_available']:continue
 parts.append('<article><img loading="lazy" alt="Public profile or page image" src="/images/'+e(p['filename'])+'"><h3>'+e(p['name_seed'])+'</h3><a href="'+e(p['profile_url'],quote=True)+'">'+e(p['title'])+'</a><p>'+str(p['width'])+'×'+str(p['height'])+' · identity unverified</p></article>')
parts.append('</div><details><summary>All candidate links and extraction status</summary>')
for p in checked:parts.append('<p><a href="'+e(p['profile_url'],quote=True)+'">'+e(p['title'])+'</a> — '+('Picture downloaded' if p['picture_available'] else e(p.get('error','Unavailable')))+'</p>')
parts.append('</details>');(static/'facebook-name-results.html').write_text(''.join(parts))
print(json.dumps({k:v for k,v in report.items() if k not in ['searches','profiles','note']}),flush=True)
