# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import csv,json,datetime,urllib.request,concurrent.futures,io,hashlib,zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from PIL import Image,ImageOps,ImageDraw
base=Path(str(_WORKSPACE_ROOT / 'research'));out=base/'creator-images';(out/'images').mkdir(parents=True,exist_ok=True)
old=list(csv.DictReader((base/'asian-male-creators-20-30.csv').open()))
records=[]
for r in old:
 records.append(dict(id=r['bio_source_url'].split('/')[-1][:-5],name=r['name'],date_of_birth=r['date_of_birth'],age=int(r['age_as_of_2026_10_31']),source_label=r['publicly_reported_background'],niche=r['niche'],platform=r['platform'],reported_audience=int(r['reported_audience_lower_bound_approx']),profile_url=r['profile_url'],biography_source=r['bio_source_url']))
extra={r['slug']:r for fn in ['expanded-sources.json','expanded2-sources.json'] for r in json.load((base/fn).open()) if 'error' not in r}
new=[('freddie-liu','Fred Liu','2002-01-18','Asian-American','Comedy/POV','TikTok',1600000,'https://www.tiktok.com/@asapliu'),('eric-ou','Eric Ou','2005-05-11','Asian heritage; American','College/lifestyle/POV','TikTok',310000,'https://www.tiktok.com/@ericcouu'),('regie-macalino','Regie Macalino','2001-02-23','Philippines-born; North Star Boys member','Comedy/dance','Instagram',280000,'https://www.instagram.com/regiemacalino/'),('sebastian-moy','Sebastian Moy','2003-04-11','Asian-American collective North Star Boys member','Comedy/lifestyle','Instagram',1500000,'https://www.instagram.com/sebastianmoy/'),('oliver-moy','Oliver Moy','2001-03-07','Asian-American collective North Star Boys member','Lip-sync/lifestyle','TikTok',11000000,'https://www.tiktok.com/@olivermoy'),('darren-liang','Darren Liang','2002-05-23','Asian-American collective North Star Boys member','Fashion/lip-sync','TikTok',1100000,'https://www.tiktok.com/@lildarbear'),('kane-ratan','Kane Ratan','1999-06-25','Asian-American collective North Star Boys member','Volleyball/comedy','TikTok',1900000,'https://www.tiktok.com/@kaneratan'),('ryan-nguyen','Ryan Nguyen','2001-07-30','Asian-American collective North Star Boys member','Fashion/POV','TikTok',2100000,'https://www.tiktok.com/@azngami'),('justin-phan','Justin Phan','2000-12-24','Asian-American collective North Star Boys member','Lip-sync/gaming','TikTok',1700000,'https://www.tiktok.com/@justin.phan')]
asof=datetime.date(2026,10,31)
for slug,name,dob,label,niche,platform,audience,profile in new:
 d=datetime.date.fromisoformat(dob);age=asof.year-d.year-((asof.month,asof.day)<(d.month,d.day))
 records.append(dict(id=slug,name=name,date_of_birth=dob,age=age,source_label=label,niche=niche,platform=platform,reported_audience=audience,profile_url=profile,biography_source=extra[slug]['url']))
def fetch(r):
 try:
  req=urllib.request.Request(r['biography_source'],headers={'User-Agent':'Mozilla/5.0'})
  html=urllib.request.urlopen(req,timeout=20).read();soup=BeautifulSoup(html,'html.parser');url=soup.find('meta',property='og:image')['content']
  if 'large-default' in url:raise ValueError('Generic placeholder excluded')
  raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read()
  with Image.open(io.BytesIO(raw)) as im:
   im=ImageOps.exif_transpose(im).convert('RGB');im.save(out/'images'/(r['id']+'.jpg'),quality=95)
   r.update(width=im.width,height=im.height)
  r.update(filename=r['id']+'.jpg',image_url=url,image_sha256=hashlib.sha256((out/'images'/r['id']).with_suffix('.jpg').read_bytes()).hexdigest(),image_download_status='ok')
 except Exception as e:r.update(image_download_status='failed: '+str(e))
 r.update(age_as_of=str(asof),audience_note='Secondary biography count; not live platform verification',photo_date=None,adult_at_capture_verified=False,license_name='Not established; public accessibility does not establish reuse rights',label_basis='Public biography; collective membership where stated',label_source='https://www.famousbirthdays.com/people/kane-ratan.html' if 'collective' in r['source_label'] else r['biography_source'])
 return r
records=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(fetch,records))
manifest={'dataset':'Asian male creators aged 20–30; public-source discovery','retrieved_date':str(asof),'minimum_audience':10000,'pictures':records,'notes':'Unscored inputs. Birthdays and audience figures from secondary biographies. Current adult age does not verify age when a photograph was taken. Photo dates and reuse rights unverified. No ethnicity inferred from photos. Not yet imported into score/rank_api.py.'}
(out/'manifest.json').write_text(json.dumps(manifest,indent=2))
fields=list(dict.fromkeys(k for r in records for k in r))
with (out/'creators.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(records)
(out/'README.txt').write_text('16 creator records, including the original seven. JPEGs are in images/. manifest.json and creators.csv retain biography, profile, original image URL, dimensions and SHA-256.\nThe score repository rank_api.py does not yet accept this collection. No scoring calls have been made.\nPhotos come from public Famous Birthdays biography metadata; license/reuse rights and photo dates are not established. Current ages do not verify adult status at capture.\nThreshold: 10,000, no maximum. All discovered matches in this batch exceed 100,000; lowering the threshold did not itself yield micro-creators. Counts are secondary bio figures.\n')
thumbs=[r for r in records if r['image_download_status']=='ok'];sheet=Image.new('RGB',(800,260*((len(thumbs)+3)//4)),'white');draw=ImageDraw.Draw(sheet)
for i,r in enumerate(thumbs):
 im=Image.open(out/'images'/r['filename']);im.thumbnail((190,220));x=(i%4)*200;y=(i//4)*260;sheet.paste(im,(x+(200-im.width)//2,y));draw.text((x+5,y+225),r['name'],fill='black')
sheet.save(out/'contact-sheet.jpg',quality=90)
with zipfile.ZipFile(base/'creator-images.zip','w',zipfile.ZIP_DEFLATED) as z:
 for p in out.rglob('*'):
  if p.is_file():z.write(p,p.relative_to(out))
print(json.dumps({'records':len(records),'images':len(thumbs),'failures':[r['name'] for r in records if r['image_download_status']!='ok'],'archive':str(base/'creator-images.zip')}))
