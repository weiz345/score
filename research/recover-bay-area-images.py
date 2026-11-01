"""Recover publicly indexed thumbnails tied to the exact discovered profile URL."""
import runpy,sys,json,os,io,hashlib,time,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit
import requests
from PIL import Image,ImageOps,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_local import load_local_environment
load_local_environment();m=runpy.run_path(str(ROOT/'research'/'discover-bay-area.py'));OUT=m['OUT'];DATA=m['DATA'];STATIC=m['STATIC'];fetch=m['fetch_public'];profile=m['profile']
m['STATE'].update(json.loads((OUT/'progress.json').read_text()));progress=m['progress']
rows=json.loads((OUT/'results.json').read_text())['pictures']
def work(row):
 row=dict(row);cache=OUT/('image-search-'+row['id']+'.json')
 try:
  if cache.exists():result=json.loads(cache.read_text())
  else:
   handle=urlsplit(row['profile_url']).path.strip('/')
   s=requests.Session();s.trust_env=False
   r=s.post('https://google.serper.dev/images',headers={'X-API-KEY':os.environ['SERPER_API_KEY']},json={'q':handle+' facebook profile picture'},timeout=(5,20))
   if r.status_code!=200:raise ValueError('Image search HTTP '+str(r.status_code))
   result=r.json();cache.write_text(json.dumps(result,indent=2))
  matches=[p for p in result.get('images',[])[:10] if profile(p.get('link',''))==row['profile_url']]
  if not matches:raise ValueError('No indexed image tied to this exact profile')
  chosen=matches[0];url=chosen.get('thumbnailUrl')
  if not url:raise ValueError('No public indexed thumbnail')
  body,final=fetch(url,10000000)
  with Image.open(io.BytesIO(body)) as im:
   if min(im.size)<100 or im.width*im.height>25000000:raise ValueError('Unsuitable thumbnail dimensions')
   im.load();im=ImageOps.exif_transpose(im).convert('RGB');filename='bay-'+row['id']+'.jpg';im.save(DATA/'images'/filename,quality=95)
   row.update(picture_available=True,filename=filename,width=im.width,height=im.height,image_url=final,image_sha256=hashlib.sha256(body).hexdigest(),image_source_page=chosen['link'],image_source_title=chosen.get('title',''),image_quality_note='Google-indexed public thumbnail tied to this profile URL; current photo and identity not independently verified',retrieval_method='Google Images indexed thumbnail')
 except Exception as exc:row.update(picture_available=False,error=str(exc)[:150] if isinstance(exc,ValueError) else type(exc).__name__)
 return row
progress(stage='recovering indexed public thumbnails',thumbnail_queries_planned=len(rows),thumbnail_queries_done=0)
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for i,f in enumerate(as_completed([pool.submit(work,r) for r in rows]),1):
  results.append(f.result())
  progress(thumbnail_queries_done=i,pictures_available=sum(p['picture_available'] for p in results))
results.sort(key=lambda p:p['profile_url']);counts={}
for p in results:
 if p['picture_available']:counts[p['image_sha256']]=counts.get(p['image_sha256'],0)+1
for p in results:
 if p['picture_available'] and counts[p['image_sha256']]>1:p.update(picture_available=False,error='Identical image across profiles excluded')
valid=[p for p in results if p['picture_available']]
m['write'](OUT/'results.json',{'pictures':results});m['write'](OUT/'review-index.json',valid)
for batch in range((len(valid)+11)//12):
 sub=valid[batch*12:(batch+1)*12];sheet=Image.new('RGB',(880,((len(sub)+3)//4)*250),'white');draw=ImageDraw.Draw(sheet)
 for j,p in enumerate(sub):
  im=ImageOps.contain(Image.open(DATA/'images'/p['filename']),(210,210));x=j%4*220;y=j//4*250;sheet.paste(im,(x,y));draw.text((x,y+211),str(batch*12+j)+' '+p['title'][:28],fill='black');draw.text((x,y+227),p['id'][:12],fill='black')
 sheet.save(OUT/('review-'+str(batch)+'.jpg'))
progress(stage='awaiting portrait eligibility review',pictures_available=len(valid))
