"""Surname-based Bay Area discovery; reviewed public portraits, cached API scores."""
import argparse,csv,hashlib,html,io,json,os,re,sys,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed,wait,FIRST_COMPLETED
from urllib.parse import urlsplit,urljoin,parse_qs
import requests
from bs4 import BeautifulSoup
from PIL import Image,ImageOps,ImageStat
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import DATA,validate
from run_local import load_local_environment
from rank_api import analyze
OUT=DATA/'bay-area-search';STATIC=ROOT/'static';OUT.mkdir(parents=True,exist_ok=True)
SURNAMES='Chen Wang Zhang Liu Li Huang Wu Lin Yang Zhou Xu Zhao Sun Zhu Hu Chan Cheung Lam Lau Zheng Wong Tang Cheng Liang Ho'.split()
CITIES='San Francisco|San Jose|Oakland|Fremont|Berkeley|Palo Alto|Mountain View|Sunnyvale|Santa Clara|Cupertino|Milpitas|Los Altos|Menlo Park|Redwood City|San Mateo|Burlingame|Foster City|San Carlos|Belmont|South San Francisco|Daly City|San Bruno|Millbrae|San Leandro|Hayward|Union City|Newark|Pleasanton|Dublin|Livermore|Alameda|Emeryville|Walnut Creek|Concord|Richmond|San Ramon|Danville|Lafayette|Orinda|Moraga|El Cerrito|San Rafael|Novato|Mill Valley|Sausalito|Vallejo|Fairfield|Vacaville|Benicia|Napa|Santa Rosa|Petaluma|Rohnert Park|Windsor|Healdsburg|Sonoma|Bay Area|Marin County|Sonoma County|Solano County|Napa County|Contra Costa County|Alameda County|San Mateo County|Santa Clara County'.split('|')
START=time.perf_counter();STATE={'stage':'starting','surname_queries_planned':len(SURNAMES),'surname_queries_done':0,'profile_candidates':0,'location_eligible':0,'pictures_checked':0,'pictures_available':0,'review_eligible':0,'scored':0,'above_7':0,'above_7_percentage':None,'score_errors':0,'threshold':7,'comparison':'>','notes':'Names are discovery seeds, not verified ethnicity. Residence is based on public current-location statements; search indexes may be stale.'}
def write(path,data):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)
def progress(**kw):
 STATE.update(kw);STATE['elapsed_seconds']=round(time.perf_counter()-START,1)
 if STATE['scored']:STATE['above_7_percentage']=round(100*STATE['above_7']/STATE['scored'],2)
 write(OUT/'progress.json',STATE);write(STATIC/'bay-area-progress.json',STATE)
 print(json.dumps(STATE),flush=True)
def setup_page():
 (STATIC/'bay-area-progress.html').write_text('''<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Regional discovery progress</title><style>body{font:17px system-ui;background:#101522;color:#edf2fa;max-width:900px;margin:35px auto;padding:20px}a{color:#9cd8c4}pre{white-space:pre-wrap;line-height:1.7}</style><h1>Regional discovery progress</h1><a href="/static/bay-area-above-7.html">Results strictly above 7</a><p>Search → public Bay Area residence → downloadable portrait → eligibility review → API scoring. Percentage denominator: all successfully scored eligible portraits. Exclusions and API failures are separate.</p><pre id="status">Loading…</pre><script>async function update(){try{const r=await fetch('/static/bay-area-progress.json?t='+Date.now());const s=await r.json();document.getElementById('status').textContent=Object.entries(s).map(([k,v])=>k+': '+v).join('\n');}catch(e){document.getElementById('status').textContent=e.message;}}update();setInterval(update,5000);</script>''')
 if not (STATIC/'bay-area-above-7.html').exists():(STATIC/'bay-area-above-7.html').write_text('<!doctype html><meta charset="utf-8"><a href="/static/bay-area-progress.html">Batch progress</a><h1>Regional profiles scoring above 7</h1><p>Batch in progress. No results scored yet.</p>')
def profile(url):
 try:
  p=urlsplit(url);parts=[x for x in p.path.split('/') if x]
  if p.scheme!='https' or p.hostname not in ['facebook.com','www.facebook.com','m.facebook.com']:return None
  if len(parts)==1 and parts[0]=='profile.php':
   ident=parse_qs(p.query).get('id',[''])[0]
   return 'https://www.facebook.com/profile.php?id='+ident if ident.isdigit() else None
  if len(parts)==3 and parts[0]=='people' and parts[2].isdigit():return 'https://www.facebook.com/'+'/'.join(parts)+'/'
  if len(parts)==2 and parts[0]=='p' and re.fullmatch(r'[A-Za-z0-9-]+-\d+',parts[1]):return 'https://www.facebook.com/p/'+parts[1]+'/'
  if len(parts)==1 and re.fullmatch(r'[A-Za-z0-9.]+',parts[0]) and parts[0].lower() not in {'login','share','watch','reels','reel','groups','events','marketplace','help','privacy','photo.php','sharer.php','public','stories','gaming','pages','hashtag'}:return 'https://www.facebook.com/'+parts[0]+'/'
 except ValueError:pass
 return None
def location(text):
 for m in re.finditer(r'\bLives in\s+([^;·|\n]+)',text,re.I):
  loc=re.split(r'\b(?:Studied|Went to|Former|Works at|Worked at|Photos|Follow|Single|Married|Joined|Read more|See more|From)\b',m[1],maxsplit=1,flags=re.I)[0].strip(' .,;·')[:120]
  for city in sorted(CITIES,key=len,reverse=True):
   if re.search(r'(?<!\w)'+re.escape(city)+r'(?!\w)',loc,re.I):return loc
 return None
def search(surname):
 query=f'"{surname}" site:facebook.com "Lives in" ("San Francisco" OR "San Jose" OR "Oakland" OR "Fremont" OR "Bay Area") -inurl:posts -inurl:videos -inurl:groups'
 cache=OUT/('search-'+surname.lower()+'.json')
 if cache.exists():return json.loads(cache.read_text())
 s=requests.Session();s.trust_env=False
 response=s.post('https://google.serper.dev/search',headers={'X-API-KEY':os.environ['SERPER_API_KEY']},json={'q':query,'num':10},timeout=(5,20))
 if response.status_code!=200:return {'surname':surname,'query':query,'error':'Search HTTP '+str(response.status_code),'organic':[]}
 result={'surname':surname,'query':query,'organic':response.json().get('organic',[])[:10]};write(cache,result);return result
def fetch_public(url,limit):
 s=requests.Session();s.trust_env=False;start=time.perf_counter()
 for _ in range(3):
  validate(url)
  with s.get(url,headers={'User-Agent':'ProfileGallery/1.0'},timeout=(3,6),stream=True,allow_redirects=False) as r:
   if r.status_code in [301,302,303,307,308]:url=urljoin(url,r.headers.get('Location',''));continue
   r.raise_for_status();body=bytearray()
   for chunk in r.iter_content(65536):
    body.extend(chunk)
    if len(body)>limit or time.perf_counter()-start>20:raise ValueError('Download limit exceeded')
   return bytes(body),url
 raise ValueError('Public page redirect limit reached')
def extract(row):
 row=dict(row);saved=OUT/'pictures'/(row['id']+'.json')
 if saved.exists():return json.loads(saved.read_text())
 try:
  body,final=fetch_public(row['profile_url'],2000000);soup=BeautifulSoup(body,'html.parser')
  images=[m['content'] for m in soup.select('meta[property="og:image"],meta[name="twitter:image"]') if m.get('content')]
  if not images:raise ValueError('No public image metadata')
  image=urljoin(final,images[0])
  if any(s in image.lower() for s in ['/rsrc.php','facebook-logo','silhouette','default_avatar']):raise ValueError('Default image excluded')
  raw,image=fetch_public(image,10000000)
  with Image.open(io.BytesIO(raw)) as im:
   if min(im.size)<100 or im.width*im.height>25000000:raise ValueError('Unsuitable image dimensions')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB')
   if max(ImageStat.Stat(im.resize((32,32))).stddev)<5:raise ValueError('Blank image excluded')
   filename='bay-'+row['id']+'.jpg';im.save(DATA/'images'/filename,quality=95)
   row.update(picture_available=True,filename=filename,width=im.width,height=im.height,image_url=image,image_sha256=hashlib.sha256(raw).hexdigest())
 except Exception as e:row.update(picture_available=False,error=str(e)[:160] if isinstance(e,ValueError) else type(e).__name__)
 write(saved,row);return row
def discover():
 searches=[];candidates={};progress(stage='surname searches')
 with ThreadPoolExecutor(max_workers=4) as pool:
  for f in as_completed([pool.submit(search,n) for n in SURNAMES]):
   try:r=f.result()
   except Exception as e:r={'error':type(e).__name__,'organic':[]}
   searches.append(r)
   for item in r['organic']:
    url=profile(item.get('link',''))
    if not url:continue
    text=item.get('snippet','');evidence=location(text)
    if not evidence:continue
    if re.search(r'\b(?:high school student|middle school|age (?:1[0-7]|[0-9])\b)',text,re.I):continue
    if url not in candidates:candidates[url]={'id':hashlib.sha256(url.encode()).hexdigest()[:24],'profile_url':url,'title':item.get('title','Public profile'),'snippet':text,'location':evidence,'location_source':item['link'],'name_seed':r.get('surname',''),'location_basis':'Public profile search snippet explicitly states Lives in; index may be stale'}
   progress(surname_queries_done=len(searches),profile_candidates=sum(bool(profile(x.get('link',''))) for sr in searches for x in sr['organic']),location_eligible=len(candidates))
 write(OUT/'searches.json',searches);write(OUT/'candidates.json',list(candidates.values()));progress(stage='extracting public pictures')
 (OUT/'pictures').mkdir(exist_ok=True);results=[]
 with ThreadPoolExecutor(max_workers=5) as pool:
  for f in as_completed([pool.submit(extract,p) for p in candidates.values()]):
   results.append(f.result());progress(pictures_checked=len(results),pictures_available=sum(p['picture_available'] for p in results))
 hashes={}
 for p in results:
  if p['picture_available']:hashes[p['image_sha256']]=hashes.get(p['image_sha256'],0)+1
 for p in results:
  if p['picture_available'] and hashes[p['image_sha256']]>1:p.update(picture_available=False,error='Shared identical image excluded')
 results.sort(key=lambda p:p['profile_url']);write(OUT/'results.json',{'pictures':results})
 valid=[p for p in results if p['picture_available']]
 from PIL import ImageDraw
 for batch in range((len(valid)+11)//12):
  subset=valid[batch*12:(batch+1)*12];sheet=Image.new('RGB',(880,((len(subset)+3)//4)*250),'white');draw=ImageDraw.Draw(sheet)
  for j,p in enumerate(subset):
   im=ImageOps.contain(Image.open(DATA/'images'/p['filename']),(210,210));x=j%4*220;y=j//4*250;sheet.paste(im,(x,y));draw.text((x,y+211),str(batch*12+j)+' '+p['title'][:28].encode('ascii','replace').decode(),fill='black')
  sheet.save(OUT/('review-'+str(batch)+'.jpg'))
 write(OUT/'review-index.json',valid);progress(stage='awaiting portrait eligibility review',pictures_available=len(valid))
def score(token):
 index=json.loads((OUT/'review-index.json').read_text());review=json.loads((OUT/'review.json').read_text());eligible=[p for p in index if p['id'] in review['eligible_ids']]
 previous=json.loads((OUT/'progress.json').read_text());STATE.update(previous);progress(stage='scoring',review_eligible=len(eligible))
 cache_path=DATA/'service'/'cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {};scored=[];errors=[];stopped=False;durations=[]
 def publish():
  scored.sort(key=lambda p:(-p['score'],p['id']));kept=[p for p in scored if p['score']>7]
  progress(stage='stopped on API error' if stopped else 'scoring',scored=len(scored),above_7=len(kept),score_errors=len(errors))
  report={'pictures':kept,'scored_count':len(scored),'above_7_count':len(kept),'above_7_percentage':round(100*len(kept)/len(scored),2) if scored else None,'eligible_count':len(eligible),'excluded_count':len(index)-len(eligible),'errors':errors,'comparison':'> 7','score_field':'raw API score','request_seconds':durations,'stopped':stopped}
  write(OUT/'ranking-summary.json',report);write(OUT/'all-scores.json',scored);write(STATIC/'bay-area-above-7.json',report);write(cache_path,cache)
  e=html.escape;parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Regional profiles · scores above 7</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}article{padding:16px;background:#1c2638;border-radius:12px;overflow-wrap:anywhere}img{width:100%;aspect-ratio:1;object-fit:contain}p{line-height:1.6}</style><a href="/static/bay-area-progress.html">Batch progress and counts</a><h1>Regional profiles · scores strictly above 7</h1>',f'<p>{len(kept)} of {len(scored)} successfully scored portraits are above 7 ({report["above_7_percentage"] if scored else "pending"}%). {len(eligible)} eligible for scoring; {report["excluded_count"]} images excluded at review; {len(errors)} API errors. Subjective API estimates, not validated on this batch. Names do not establish ethnicity. Location comes from indexed public residence statements and may be stale.</p><a href="/static/bay-area-above-7.csv">Download qualifying results</a><div class="grid">']
  for i,p in enumerate(kept,1):parts.append('<article><img loading="lazy" alt="Public profile portrait" src="/images/'+e(p['filename'])+'"><h2>#'+str(i)+' · '+format(p['score'],'.2f')+' / 10</h2><a href="'+e(p['profile_url'],quote=True)+'">'+e(p['title'])+'</a><p>'+e(p['location'])+'</p><p>'+str(p['width'])+'×'+str(p['height'])+' pixels · '+e(p.get('image_quality_note','Public portrait'))+'</p><p>Adjusted API score: '+format(p['score_adjusted'],'.2f')+'</p><a title="'+e(p['snippet'],quote=True)+'" href="'+e(p['location_source'],quote=True)+'">Location evidence</a></article>')
  parts.append('</div>');(STATIC/'bay-area-above-7.html').write_text(''.join(parts))
  render_all_gallery(scored,report)
  with (STATIC/'bay-area-above-7.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=['title','profile_url','score','score_adjusted','location','location_source','filename'],extrasaction='ignore');w.writeheader();w.writerows(kept)
 def work(p):
  start=time.perf_counter();raw=(DATA/'images'/p['filename']).read_bytes();platform='instagram' if 'instagram.com' in p['profile_url'] else 'linkedin' if 'linkedin.com' in p['profile_url'] else 'facebook';key=platform+':'+hashlib.sha256(p['profile_url'].encode()).hexdigest()[:24]+':'+hashlib.sha256(raw).hexdigest()
  if key in cache:return p,key,cache[key],None,0
  try:
   s=requests.Session();s.trust_env=False;r=analyze(s,raw,token);return p,key,r,None,round(time.perf_counter()-start,3)
  except Exception as e:return p,key,None,str(e)[:140] if isinstance(e,(RuntimeError,ValueError)) else type(e).__name__,round(time.perf_counter()-start,3)
 iterator=iter(eligible)
 with ThreadPoolExecutor(max_workers=3) as pool:
  running={pool.submit(work,p) for p in [next(iterator,None) for _ in range(3)] if p}
  while running:
   done,running=wait(running,return_when=FIRST_COMPLETED)
   for f in done:
    p,key,r,error,duration=f.result()
    if duration:durations.append(duration)
    if error:
     errors.append({'id':p['id'],'profile_url':p['profile_url'],'error':error})
     if 'HTTP 400;' not in error and 'HTTP 422;' not in error:stopped=True
    else:cache[key]=r;scored.append(dict(p,**r))
    publish()
   if not stopped:
    while len(running)<3:
     p=next(iterator,None)
     if p is None:break
     running.add(pool.submit(work,p))
 publish();progress(stage='stopped on API error' if stopped else 'complete')

def render_all_gallery(scored,report):
 e=html.escape
 write(STATIC/'regional-all-scores.json',scored)
 parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Regional profile scores</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}article{padding:16px;background:#1c2638;border-radius:12px;overflow-wrap:anywhere}img{width:100%;aspect-ratio:1;object-fit:contain}p{line-height:1.6}</style><a href="/static/bay-area-progress.html">Progress</a> · <a href="/static/bay-area-above-7.html">Only scores above 7</a><h1>Regional profile scores</h1>',f'<p><b>{report["above_7_count"]} of {report["scored_count"]} successfully scored portraits are above 7: {report["above_7_percentage"] if scored else "pending"}%.</b> Every successfully scored eligible portrait is retained. Names do not establish ethnicity. Public location information may be stale. Subjective API scores are affected by image quality and are not validated on this sample.</p><p><label>Show <select id="score-filter"><option value="all">Everyone scored</option><option value="above">Only above 7</option></select></label> <label>Region <select id="region"><option value="all">All target regions</option><option>Bay Area</option><option>Vancouver BC</option><option>Toronto</option><option>Los Angeles</option></select></label> <span id="count"></span> · <a href="/static/regional-all-scores.csv">Download all scores</a></p><div class="grid">']
 for i,p in enumerate(scored,1):
  parts.append('<article data-score="'+str(p['score'])+'" data-region="'+e(p.get('region','Bay Area'),quote=True)+'"><img loading="lazy" alt="Public portrait" src="/images/'+e(p['filename'])+'"><h2>#'+str(i)+' · '+format(p['score'],'.2f')+' / 10</h2><a href="'+e(p['profile_url'],quote=True)+'">'+e(p['title'])+'</a><p>'+e(p['location'])+'</p><p>'+str(p['width'])+'×'+str(p['height'])+' pixels</p><p>'+e(p.get('image_quality_note','Public portrait'))+'</p><p>Adjusted API score: '+format(p['score_adjusted'],'.2f')+'</p><a title="'+e(p['snippet'],quote=True)+'" href="'+e(p['location_source'],quote=True)+'">Location evidence</a></article>')
 parts.append('</div><script>function filter(){let n=0;for(const c of document.querySelectorAll("article")){c.hidden=(document.getElementById("score-filter").value==="above"&&Number(c.dataset.score)<=7)||(document.getElementById("region").value!=="all"&&c.dataset.region!==document.getElementById("region").value);if(!c.hidden)n++;}document.getElementById("count").textContent=n+" profiles";}document.getElementById("score-filter").onchange=filter;document.getElementById("region").onchange=filter;filter();</script>')
 (STATIC/'regional-ranked.html').write_text(''.join(parts))
 with (STATIC/'regional-all-scores.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=['title','profile_url','score','score_adjusted','region','location','width','height'],extrasaction='ignore');w.writeheader();w.writerows(scored)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',choices=['discover','score'],default='discover');args=parser.parse_args();load_local_environment();setup_page()
 if args.stage=='discover':discover()
 else:score(os.environ['ATTRACTIVENESS_API_TOKEN'])
