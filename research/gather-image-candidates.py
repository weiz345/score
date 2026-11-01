"""Collect public profile links plus indexed images; no scoring or face inference."""
import os,sys,json,re,csv,io,hashlib,time,threading,argparse,html
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
from urllib.parse import urlsplit,parse_qs
from collections import Counter
import requests
from PIL import Image,ImageOps
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_local import load_local_environment
from profile_search import profile_url
from app import DATA,validate
load_local_environment()
SURNAMES='Chen Wang Zhang Liu Li Huang Wu Lin Yang Zhou Xu Zhao Sun Zhu Hu Chan Cheung Lam Lau Zheng Wong Tang Cheng Liang Ho'.split()
REGIONS=['San Francisco Bay Area','Vancouver BC','Toronto','Los Angeles']
PLATFORMS=['Instagram','Facebook','LinkedIn']
OUT=DATA/'candidate-collection';OUT.mkdir(exist_ok=True);(OUT/'searches').mkdir(exist_ok=True);(OUT/'pictures').mkdir(exist_ok=True)
STATIC=ROOT/'static';START=time.perf_counter();LOCAL=threading.local()
def session():
 if not hasattr(LOCAL,'session'):LOCAL.session=requests.Session();LOCAL.session.trust_env=False
 return LOCAL.session
def save(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
def canonical(url):
 direct=profile_url(url)
 if direct:return direct.lower()
 try:
  p=urlsplit(url);parts=[x for x in p.path.split('/') if x]
  if p.scheme!='https' or p.hostname not in ['facebook.com','www.facebook.com','m.facebook.com']:return None
  if len(parts)==1 and parts[0]=='profile.php':
   ident=parse_qs(p.query).get('id',[''])[0]
   return 'https://www.facebook.com/profile.php?id='+ident if ident.isdigit() else None
  if len(parts)==3 and parts[0]=='people' and parts[2].isdigit():return 'https://www.facebook.com/'+'/'.join(parts)+'/'
  if len(parts)==2 and parts[0]=='p' and re.fullmatch(r'[A-Za-z0-9-]+-\d+',parts[1]):return 'https://www.facebook.com/p/'+parts[1]+'/'
  if len(parts)==1 and re.fullmatch(r'[A-Za-z0-9.]+',parts[0]) and parts[0].lower() not in {'login','share','watch','reels','reel','groups','events','marketplace','help','privacy','photo.php','sharer.php','public','stories','gaming','pages','hashtag','search','photo','photos','videos','video.php','story.php','permalink.php','checkpoint','recover','settings','business','ads','directory','friends','messages','notifications','bookmarks','home.php','plugins','dialog','login.php'}:return 'https://www.facebook.com/'+parts[0].lower()+'/'
 except ValueError:pass
 return None
def platform(url):return 'Instagram' if 'instagram.com' in url else 'LinkedIn' if 'linkedin.com' in url else 'Facebook'
def search(job):
 surname,region,site=job;query=f'{surname} {region} {site} profile';key=hashlib.sha256(query.encode()).hexdigest()[:24];path=OUT/'searches'/(key+'.json')
 if path.exists():return json.loads(path.read_text())
 t=time.perf_counter()
 try:
  r=session().post('https://google.serper.dev/images',headers={'X-API-KEY':os.environ['SERPER_API_KEY']},json={'q':query},timeout=(5,20))
  record={'query':query,'surname':surname,'region':region,'requested_platform':site,'http_status':r.status_code,'seconds':round(time.perf_counter()-t,3),'images':r.json().get('images',[])[:100] if r.status_code==200 else []}
 except requests.RequestException as e:record={'query':query,'surname':surname,'region':region,'requested_platform':site,'error':type(e).__name__,'images':[],'seconds':round(time.perf_counter()-t,3)}
 save(path,record);return record
def download(candidate):
 path=OUT/'pictures'/(candidate['id']+'.json')
 if path.exists():
  old=json.loads(path.read_text())
  if old.get('ok') and (DATA/'images'/old['filename']).exists():return dict(candidate,**old)
 try:
  url=candidate['thumbnail_url'];validate(url)
  with session().get(url,timeout=(3,8),stream=True,allow_redirects=False) as r:
   r.raise_for_status();raw=bytearray()
   for chunk in r.iter_content(65536):
    raw.extend(chunk)
    if len(raw)>4000000:raise ValueError('Image size limit exceeded')
  with Image.open(io.BytesIO(raw)) as im:
   if min(im.size)<48 or im.width*im.height>12000000:raise ValueError('Image dimensions excluded')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB');filename='candidate-'+candidate['id']+'.jpg';im.save(DATA/'images'/filename,quality=95)
   result=dict(candidate,ok=True,filename=filename,width=im.width,height=im.height,image_sha256=hashlib.sha256(raw).hexdigest(),image_kind='Google-indexed image associated with this profile URL; identity, currentness and portrait status unverified')
 except Exception as exc:result=dict(candidate,ok=False,error=str(exc)[:120] if isinstance(exc,ValueError) else type(exc).__name__)
 save(path,result);return result
def main(limit):
 (STATIC/'candidate-gathering.html').write_text((ROOT/'templates'/'candidates.html').read_text())
 jobs=[(surname,region,site) for surname in SURNAMES for region in REGIONS for site in PLATFORMS][:limit]
 candidates={};downloaded={};failed={};stats={'stage':'gathering','queries_planned':len(jobs),'queries_completed':0,'image_search_results':0,'unique_profile_links':0,'downloadable_candidates':0,'image_failures':0,'query_failures':0,'ratings_requested':0,'regions':REGIONS,'note':'Query regions are discovery hints, not verified residence. Names are search seeds, not verified ethnicity. Photos may be nonportraits or stale; no face matching, age inference or scoring.'};durations=[];queries=[]
 def publish(force=False):
  good=[]
  for ident,row in downloaded.items():
   merged=dict(row);merged.update(queried_regions=sorted(candidates[ident]['queried_regions']),name_seeds=sorted(candidates[ident]['name_seeds']));good.append(merged)
  good.sort(key=lambda p:(p['title'].casefold(),p['profile_url']))
  stats.update(elapsed_seconds=round(time.perf_counter()-START,1),unique_profile_links=len(candidates),downloadable_candidates=len(good),image_failures=len(failed),platform_counts=dict(Counter(p['platform'] for p in good)),mean_search_seconds=round(sum(durations)/len(durations),2) if durations else None)
  save(OUT/'progress.json',stats);save(STATIC/'candidate-gathering-progress.json',stats)
  save(OUT/'candidates.json',good);save(STATIC/'gathered-candidates.json',good)
  with (STATIC/'gathered-candidates.csv').open('w') as f:
   fields=['id','title','platform','handle','profile_url','width','height','filename','queried_regions','name_seeds','location_status','image_kind'];w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
   for row in good:w.writerow(dict(row,queried_regions='; '.join(row['queried_regions']),name_seeds='; '.join(row['name_seeds'])))
  if force:print(json.dumps(stats),flush=True)
 iterator=iter(jobs);stopped=False;last_publish=0
 with ThreadPoolExecutor(max_workers=4) as searches,ThreadPoolExecutor(max_workers=8) as pictures:
  active_search={searches.submit(search,j) for j in [next(iterator,None) for _ in range(4)] if j};active_pictures={}
  while active_search or active_pictures:
   done,_=wait(active_search|set(active_pictures),return_when=FIRST_COMPLETED)
   for future in done:
    if future in active_search:
     active_search.remove(future);record=future.result();queries.append(record);stats['queries_completed']+=1;durations.append(record.get('seconds',0));stats['image_search_results']+=len(record['images'])
     if record.get('http_status',200)!=200 or record.get('error'):stats['query_failures']+=1
     if record.get('http_status') in [401,402,403,429]:stopped=True;stats['stage']='stopped after provider error'
     for image in record['images']:
      url=canonical(image.get('link',''))
      if not url or not image.get('thumbnailUrl'):continue
      title=image.get('title','')
      if not re.search(r'(?<!\w)'+re.escape(record['surname'])+r'(?!\w)',title,re.I):continue
      ident=hashlib.sha256(url.encode()).hexdigest()[:24]
      if ident in candidates:
       candidates[ident]['queried_regions'].add(record['region']);candidates[ident]['name_seeds'].add(record['surname']);continue
      row={'id':ident,'title':title,'profile_url':url,'handle':('id='+parse_qs(urlsplit(url).query).get('id',[''])[0] if urlsplit(url).path=='/profile.php' else urlsplit(url).path.strip('/')),'platform':platform(url),'thumbnail_url':image['thumbnailUrl'],'original_image_url':image.get('imageUrl',''),'queried_regions':{record['region']},'name_seeds':{record['surname']},'location_status':'Query match only; residence unverified','image_source_url':image.get('link','')}
      candidates[ident]=row;copy=dict(row,queried_regions=list(row['queried_regions']),name_seeds=list(row['name_seeds']));f=pictures.submit(download,copy);active_pictures[f]=ident
    else:
     ident=active_pictures.pop(future);row=future.result()
     if row['ok']:downloaded[ident]=row
     else:failed[ident]=row
   if not stopped:
    while len(active_search)<4 and len(active_pictures)<128:
     job=next(iterator,None)
     if job is None:break
     active_search.add(searches.submit(search,job))
   now=time.perf_counter()
   if now-last_publish>2 or not active_search and not active_pictures:
    publish(force=stats['queries_completed']%10==0 or now-last_publish>10);last_publish=now
  stats['stage']='stopped after provider error' if stopped else 'complete';publish(force=True)
 save(OUT/'queries-summary.json',[{k:v for k,v in r.items() if k!='images'} for r in queries]);save(OUT/'image-failures.json',list(failed.values()))
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--queries',type=int,default=300);args=parser.parse_args();main(args.queries)
