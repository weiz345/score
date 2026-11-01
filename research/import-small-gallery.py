# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import json,re,datetime,urllib.request,concurrent.futures,hashlib,io,csv
from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
root=Path(str(_WORKSPACE_ROOT));out=root/'data/small-creators';(out/'images').mkdir(parents=True,exist_ok=True)
rs=[]
for fn in ['smaller-discovery.json','tiny-discovery.json']:rs+=json.load(open(str(_WORKSPACE_ROOT / 'research') + '/'+fn))
selected=['nyao','diana-bakar','juhi-nars','chrysan-lee','yuyumonster','amelia-neo','tessa-tessasus','eleena-harris','sym','sheryl-ng','paia-lee','happy-polla','honeebell','michelle-karla','scott-sodbiligt']
by={r['url'].split('/')[-1][:-5]:r for r in rs if 'error' not in r}
handles={'nyao':'nyaomaruu','diana-bakar':'dianabakar_','yuyumonster':'YUYUmonster','amelia-neo':'amelia_neo','tessa-tessasus':'Tessasus','eleena-harris':'eleenaharris','sym':'syame31','paia-lee':'paialee','honeebell':'honeebell'}
labels={'nyao':'Japan-born','diana-bakar':'Singapore-born','juhi-nars':'Singaporean','chrysan-lee':'Singapore-born','yuyumonster':'From Singapore','amelia-neo':'Singapore-born; raised in Canada','tessa-tessasus':'Singapore-born','eleena-harris':'Malaysian','sym':'Malaysian','sheryl-ng':'Malaysian','paia-lee':'Thailand-born; moved to USA','happy-polla':'From Thailand','honeebell':'Philippines-born','michelle-karla':'Indonesian','scott-sodbiligt':'Mongolian'}
asof=datetime.date(2026,10,31)
def make(slug):
 r=by[slug];t=r['text'];m=re.search(r'Birthday (\w+ \d+) , (\d{4}) Birth',t)
 dob=datetime.datetime.strptime(m[1]+' '+m[2],'%B %d %Y').date();age=asof.year-dob.year-((asof.month,asof.day)<(dob.month,dob.day))
 if not 20<=age<=30:raise ValueError('Outside age range')
 url=r['image_url']
 if not url or 'large-default' in url:raise ValueError('No actual public picture')
 raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read()
 with Image.open(io.BytesIO(raw)) as im:
  im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((800,800));im.save(out/'images'/f'{slug}.jpg',quality=92);width,height=im.size
 gender='Men' if slug in ['sym','scott-sodbiligt'] else 'Women'
 audience=max(r['counts']);platform='Instagram';audience_note='Reported in secondary biography; live count not verified.'
 if slug=='honeebell':audience=20000;platform='Twitch';audience_note+=' Bio also reports 70,000 on Instagram.'
 if slug=='scott-sodbiligt':platform='All platforms combined';audience_note+=' Combined total, not a per-platform count.'
 handle=handles.get(slug,'')
 return dict(id=slug,name=r['name'],participant=r['name'],filename=f'{slug}.jpg',width=width,height=height,age=age,birthdate=str(dob),age_as_of=str(asof),age_range=f'{age} years old · as of {asof}',gender=gender,gender_basis='Public biography language; not inferred from picture',source_label=labels[slug],label_basis='Public biography origin/nationality; ethnicity not inferred',biography_source=r['url'],reported_audience=audience,platform=platform,audience_note=audience_note,profile_url=f'https://www.instagram.com/{handle}/' if handle else '',image_url=url,image_base='/dataset-images/small-creators/',display_group='creators',photo_date=None,adult_at_capture_verified=False,image_sha256=hashlib.sha256((out/'images'/f'{slug}.jpg').read_bytes()).hexdigest())
rows=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(make,selected));rows.sort(key=lambda r:r['name'].casefold())
m=dict(dataset='Smaller public creators',source='https://www.famousbirthdays.com/',license={'name':'Public source images; reuse rights not established'},attribution='Per-profile biography and original image URLs retained. Sources report origin/nationality; ethnicity is not inferred from photographs.',model='Not scored',unranked=True,method='Men and women aged 20–30. No follower minimum. Alphabetical display; no attractiveness scores or ranks.',metrics=None,image_base='/dataset-images/small-creators/',evaluation_note='Audience figures are source-reported and may be outdated. Photo dates are unknown; current ages do not establish age at capture.',pictures=rows,retrieved_date=str(asof))
(out/'rankings.json').write_text(json.dumps(m,indent=2))
fields=list(rows[0])
with (out/'creators.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
sheet=Image.new('RGB',(1000,270*((len(rows)+4)//5)),'white');draw=ImageDraw.Draw(sheet)
for i,r in enumerate(rows):
 im=Image.open(out/'images'/r['filename']);im.thumbnail((190,215));x=(i%5)*200;y=(i//5)*270;sheet.paste(im,(x+(200-im.width)//2,y));draw.text((x+4,y+220),r['name'],fill='black');draw.text((x+4,y+238),str(r['reported_audience'])+' '+r['platform'],fill='black')
sheet.save(str(_WORKSPACE_ROOT / 'research/small-creators-contact-sheet.jpg'),quality=90)
print(json.dumps({'imported':len(rows),'men':sum(r['gender']=='Men' for r in rows),'women':sum(r['gender']=='Women' for r in rows),'lowest_reported_audience':min(r['reported_audience'] for r in rows)}))
