"""Public Instagram/LinkedIn surname discovery in selected North American metros."""
import sys,os,json,re,io,hashlib,runpy,importlib.util
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit,urljoin
import requests
from PIL import Image,ImageOps,ImageDraw
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_local import load_local_environment
from profile_search import profile_url
from app import DATA
load_local_environment()
spec=importlib.util.spec_from_file_location('regional_base',ROOT/'research'/'discover-bay-area.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
OUT=DATA/'west-coast-toronto';OUT.mkdir(exist_ok=True);base.OUT=OUT
base.STATE.update(scope='Bay Area; Vancouver BC; Toronto; Los Angeles',surname_queries_planned=33,surname_queries_done=0)
base.setup_page();base.progress(stage='Instagram and LinkedIn discovery')
REGIONS=['San Francisco','Vancouver','Toronto','Los Angeles']
SURNAMES=base.SURNAMES
LOCATIONS={'Bay Area':r'San Francisco(?: Bay Area)?|San Jose|Oakland|Fremont|Palo Alto|Mountain View|Sunnyvale|Cupertino|Santa Clara|Berkeley|Bay Area','Vancouver BC':r'Vancouver(?:,? (?:BC|British Columbia))?|Burnaby|Richmond,? (?:BC|British Columbia)|Surrey,? (?:BC|British Columbia)','Toronto':r'Toronto|Greater Toronto Area|GTA|Mississauga|Markham|Richmond Hill','Los Angeles':r'Los Angeles|Greater Los Angeles Area|LA,? (?:CA|California)|LA[- ]based|Pasadena|Santa Monica|Burbank|Culver City|Long Beach'}
def get_location(text,platform):
 # Explicit residence/location labels or an Instagram profile bio city marker.
 text=re.sub(r'\s+',' ',text)
 for region,pattern in LOCATIONS.items():
  patterns=[r'(?:Location:|Lives in|based in|📍)\s*('+pattern+r')',r'('+pattern+r')[- ]based']
  if platform=='LinkedIn':patterns.append(r'^('+pattern+r')(?:,? California|,? Ontario|,? Canada|\s*·|\s*\|)')
  else:patterns += [r'(?:[|·•;:“]|^|followers\.\s*)\s*('+pattern+r')(?:,? (?:CA|California|Canada|BC|Ontario))?\s*(?:[|·•;”]|$)',r'\b(San Francisco Bay Area|Vancouver, British Columbia|Toronto, Ontario|Los Angeles, California)\b']
  for p in patterns:
   m=re.search(p,text,re.I)
   if m:
    if region=='Vancouver BC' and re.search(r'Vancouver,?\s*(?:Washington|WA)\b',text,re.I):continue
    return region,m[1]
 return None,None
def search(job):
 platform,surname,region=job
 query=(f'"{surname}" "{region}" "followers" site:instagram.com -inurl:reel -inurl:reels -inurl:stories -inurl:explore -inurl:/p/' if platform=='Instagram' else f'"{surname}" "{region}" site:linkedin.com/in/')
 key=hashlib.sha256(query.encode()).hexdigest()[:20];path=OUT/('query-'+key+'.json')
 if path.exists():return json.loads(path.read_text())
 try:
  s=requests.Session();s.trust_env=False;r=s.post('https://google.serper.dev/search',headers={'X-API-KEY':os.environ['SERPER_API_KEY']},json={'q':query,'num':10},timeout=(5,20))
  result={'platform':platform,'surname':surname,'region':region,'query':query,'organic':r.json().get('organic',[])[:10] if r.status_code==200 else [],'status':r.status_code}
 except requests.RequestException as e:result={'platform':platform,'surname':surname,'query':query,'organic':[],'error':type(e).__name__}
 base.write(path,result);return result
jobs=[('Instagram',name,REGIONS[i%4]) for i,name in enumerate(SURNAMES)]+[('LinkedIn',SURNAMES[i],REGIONS[i%4]) for i in range(8)]
results=[];candidates={}
with ThreadPoolExecutor(max_workers=4) as pool:
 for f in as_completed([pool.submit(search,j) for j in jobs]):
  result=f.result();results.append(result)
  for item in result['organic']:
   url=profile_url(item.get('link',''))
   if not url:continue
   if (result['platform']=='Instagram')!=('instagram.com' in url):continue
   # A surname must occur as a whole name token, not just in unrelated search text.
   title=item.get('title','')
   if not re.search(r'(?<!\w)'+re.escape(result['surname'])+r'(?!\w)',title,re.I):continue
   if re.search(r'\b(?:high school student|middle school|1[0-7] years old)\b',item.get('snippet',''),re.I):continue
   region,loc=get_location(item.get('snippet',''),result['platform'])
   candidates.setdefault(url,{'id':hashlib.sha256(url.encode()).hexdigest()[:24],'profile_url':url,'title':title,'name_seed':result['surname'],'snippet':item.get('snippet',''),'platform':result['platform'],'region':region,'location':loc,'location_source':item['link']})
  base.progress(surname_queries_done=len(results),profile_candidates=len(candidates),location_eligible=sum(bool(p['location']) for p in candidates.values()))
base.write(OUT/'searches.json',results);base.write(OUT/'candidates.json',list(candidates.values()))
base.progress(stage='extracting Instagram and LinkedIn pictures')
def extract(p):
 p=dict(p);cache=OUT/('profile-'+p['id']+'.json')
 if cache.exists():return json.loads(cache.read_text())
 try:
  body,final=base.fetch_public(p['profile_url'],2000000);soup=BeautifulSoup(body,'html.parser')
  metas={m.get('property',m.get('name','')):m.get('content','') for m in soup.find_all('meta')}
  if not p['location']:
   region,loc=get_location(metas.get('og:description',''),p['platform'])
   if loc:p.update(region=region,location=loc,location_source=p['profile_url'],location_evidence=metas['og:description'])
  if not p['location']:raise ValueError('No explicit public target-region location')
  image=metas.get('og:image') or metas.get('twitter:image')
  if not image:raise ValueError('No public image metadata')
  image=urljoin(final,image)
  if any(s in image.lower() for s in ['/rsrc.php','ghost-person','default_avatar','default_profile','company-logo']):raise ValueError('Default or site image excluded')
  raw,image=base.fetch_public(image,10000000)
  with Image.open(io.BytesIO(raw)) as im:
   if min(im.size)<100 or im.width*im.height>25000000:raise ValueError('Unsuitable image dimensions')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB');filename='regional-'+p['id']+'.jpg';im.save(DATA/'images'/filename,quality=95)
   p.update(picture_available=True,filename=filename,width=im.width,height=im.height,image_url=image,image_sha256=hashlib.sha256(raw).hexdigest(),image_quality_note='Low-resolution thumbnail; scores sensitive to photo quality' if min(im.size)<300 else 'Public profile image',location_basis='Explicit location in public profile metadata or indexed profile snippet; may be stale')
 except Exception as e:p.update(picture_available=False,error=str(e)[:160] if isinstance(e,ValueError) else type(e).__name__)
 base.write(cache,p);return p
pictures=[]
# Check every Instagram candidate; LinkedIn candidates without a location need no fetch.
targets=[p for p in candidates.values() if p['platform']=='Instagram' or p['location']]
with ThreadPoolExecutor(max_workers=5) as pool:
 for f in as_completed([pool.submit(extract,p) for p in targets]):
  pictures.append(f.result());base.progress(pictures_checked=len(pictures),pictures_available=sum(p['picture_available'] for p in pictures),location_eligible=sum(bool(p['location']) for p in pictures))
base.write(OUT/'results.json',{'pictures':pictures})
valid=sorted([p for p in pictures if p['picture_available']],key=lambda p:p['profile_url']);base.write(OUT/'review-index.json',valid)
for batch in range((len(valid)+11)//12):
 sub=valid[batch*12:(batch+1)*12];sheet=Image.new('RGB',(880,((len(sub)+3)//4)*250),'white');draw=ImageDraw.Draw(sheet)
 for j,p in enumerate(sub):
  im=ImageOps.contain(Image.open(DATA/'images'/p['filename']),(210,210));x=j%4*220;y=j//4*250;sheet.paste(im,(x,y));draw.text((x,y+211),str(batch*12+j)+' '+p['title'][:28],fill='black');draw.text((x,y+227),p['region'],fill='black')
 sheet.save(OUT/('review-'+str(batch)+'.jpg'))
base.progress(stage='awaiting portrait eligibility review',pictures_available=len(valid))
