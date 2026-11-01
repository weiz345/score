"""Find publicly indexed photos tied to exact location-qualified LinkedIn URLs."""
import sys,os,json,io,hashlib,re
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit
import requests
from PIL import Image,ImageOps,ImageDraw
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_local import load_local_environment
from profile_search import profile_url
load_local_environment()
import importlib.util
spec=importlib.util.spec_from_file_location('regional_base_images',ROOT/'research'/'discover-bay-area.py');base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
OUT=base.DATA/'west-coast-toronto'
rows=json.loads((OUT/'results.json').read_text())['pictures'];targets=[p for p in rows if p['platform']=='LinkedIn' and p['location'] and not p['picture_available']]
def work(p):
 p=dict(p);cache=OUT/('indexed-'+p['id']+'.json')
 if cache.exists():return json.loads(cache.read_text())
 try:
  name=p['title'].split(' - ')[0];q=name+' '+p['location']+' LinkedIn'
  session=requests.Session();session.trust_env=False;r=session.post('https://google.serper.dev/images',headers={'X-API-KEY':os.environ['SERPER_API_KEY']},json={'q':q},timeout=(5,20))
  if r.status_code!=200:raise ValueError('Image search HTTP '+str(r.status_code))
  payload=r.json();base.write(OUT/('indexed-search-'+p['id']+'.json'),payload)
  matches=[im for im in payload.get('images',[])[:10] if profile_url(im.get('link',''))==p['profile_url']]
  if not matches:raise ValueError('No public indexed image tied to exact LinkedIn URL')
  im=matches[0];url=im.get('imageUrl','');raw=None
  if 'licdn.com' in (urlsplit(url).hostname or ''):
   try:
    data,final=base.fetch_public(url,10000000)
    with Image.open(io.BytesIO(data)) as test:test.verify()
    raw=data;url=final
   except Exception:pass
  if raw is None:
   url=im.get('thumbnailUrl','')
   if not url:raise ValueError('No indexed thumbnail')
   raw,url=base.fetch_public(url,10000000)
  with Image.open(io.BytesIO(raw)) as image:
   if min(image.size)<100 or image.width*image.height>25000000:raise ValueError('Unsuitable image dimensions')
   image.load();image=ImageOps.exif_transpose(image).convert('RGB');filename='regional-'+p['id']+'.jpg';image.save(base.DATA/'images'/filename,quality=95)
   p.update(picture_available=True,filename=filename,width=image.width,height=image.height,image_url=url,image_source_page=im['link'],image_sha256=hashlib.sha256(raw).hexdigest(),image_quality_note='Google-indexed public image tied to exact LinkedIn URL; image may be stale'+(' · low resolution' if min(image.size)<300 else ''))
 except Exception as exc:p.update(picture_available=False,error=str(exc)[:150] if isinstance(exc,ValueError) else type(exc).__name__)
 base.write(cache,p);return p
recovered=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for i,f in enumerate(as_completed([pool.submit(work,p) for p in targets]),1):
  recovered.append(f.result());print(json.dumps({'linkedin_images_checked':i,'total':len(targets),'recovered':sum(p['picture_available'] for p in recovered)}),flush=True)
lookup={p['id']:p for p in recovered};allrows=[lookup.get(p['id'],p) for p in rows];valid=sorted([p for p in allrows if p['picture_available']],key=lambda p:p['profile_url'])
base.write(OUT/'results.json',{'pictures':allrows});base.write(OUT/'review-index.json',valid)
for batch in range((len(valid)+11)//12):
 sub=valid[batch*12:(batch+1)*12];sheet=Image.new('RGB',(880,((len(sub)+3)//4)*250),'white');draw=ImageDraw.Draw(sheet)
 for j,p in enumerate(sub):
  im=ImageOps.contain(Image.open(base.DATA/'images'/p['filename']),(210,210));x=j%4*220;y=j//4*250;sheet.paste(im,(x,y));draw.text((x,y+211),(str(batch*12+j)+' '+p['title'][:27]).encode('ascii','replace').decode(),fill='black');draw.text((x,y+227),p['region'],fill='black')
 sheet.save(OUT/('review-'+str(batch)+'.jpg'))
print(json.dumps({'usable_photos':len(valid),'new_linkedin_photos':sum(p['picture_available'] for p in recovered)}),flush=True)
