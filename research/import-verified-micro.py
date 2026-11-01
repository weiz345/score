# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import json,re,sys,urllib.request,io,hashlib,csv
from datetime import date
from pathlib import Path
from PIL import Image,ImageOps
sys.path.insert(0,str(_WORKSPACE_ROOT));from collect_instagram_batch import age_info
root=Path(str(_WORKSPACE_ROOT / 'data/small-creators'));manifest=json.loads((root/'rankings.json').read_text());checks=[]
for file in ['previous-micro-checks.json','micro-instagram-checks.json']:checks+=json.load(open(str(_WORKSPACE_ROOT / 'research') + '/'+file))
allowed={'ali_essa1','iinadora','anncxo','gyu.2','gabriellaarde','niggydy','_timasavea','firahachmad','zarahzamira'}
new=[]
for r in checks:
 handle=r['handle'].lower()
 if handle not in allowed:continue
 assert 1000<=r['followers']<=50000 and r['posts']>=10
 meta=r['metadata'];image_url=meta['og:image'];raw=urllib.request.urlopen(urllib.request.Request(image_url,headers={'User-Agent':'PublicProfileGallery/1.0'}),timeout=15).read();ident='instagram-'+handle;filename=ident+'.jpg'
 with Image.open(io.BytesIO(raw)) as im:
  im=ImageOps.exif_transpose(im).convert('RGB');im.save(root/'images'/filename,quality=92);width,height=im.size
 text=r.get('text','');age=age_info(text,date(2026,10,31));header=text.split(' About ')[0];personal=text.split(' About ',1)[-1].split(' Family life ',1)[0]
 male=bool(re.search(r'\b(?:He|His|he|his)\b',personal));female=bool(re.search(r'\b(?:She|Her|she|her)\b',personal));gender='Men' if male and not female else 'Women' if female and not male else 'Not specified'
 birthplace=re.search(r'Birthplace (.+?) (?:Age |#)',header);background='Birthplace: '+birthplace[1].strip() if birthplace else 'Background not documented'
 if handle=='anncxo':background='Public biography: born in Iran; Persian parents'
 preferred=age['age_min'] is not None and 20<=age['age_min']<=age['age_max']<=30
 row=dict(id=ident,name='Anna / @anncxo' if handle=='anncxo' else r['name'],participant=r['name'],filename=filename,width=width,height=height,**age,age_as_of='2026-10-31',gender=gender,gender_basis='Public biography language; not inferred from photo',source_label=background,label_basis='Public biography; unknown where not documented',biography_source=r['source_url'],background_source=r['source_url'],age_source=r['source_url'],profile_url=r['url'],image_url=image_url,image_base='/dataset-images/small-creators/',display_group='creators',reported_audience=r['followers'],platform='Instagram',audience_display=f"Instagram reports {r['followers']:,} followers · {r['posts']:,} posts",audience_note='Observed in public Instagram metadata; K/M figures are rounded by Instagram.',follower_count_source=r['url'],follower_count_verified_date='2026-10-31',post_count=r['posts'],recent_activity_verified=False,activity_note='Post count verified; dates of latest posts were not publicly available in fetched metadata.',preferred_age_match=preferred,photo_date=None,adult_at_capture_verified=False,image_sha256=hashlib.sha256((root/'images'/filename).read_bytes()).hexdigest())
 if handle=='iinadora':
  row.update(age_source='',background_source='',biography_source=r['url'],profile_identity_source='https://www.instagram.com/inaanjan/',source_label='Background not documented',label_basis='No ethnicity inferred',gender='Not specified')
 new.append(row)
old_ids={r['id'] for r in new};manifest['pictures']=[r for r in manifest['pictures'] if r['id'] not in old_ids]+new;manifest['pictures'].sort(key=lambda r:r['name'].casefold());manifest['updated_date']='2026-10-31'
(root/'rankings.json').write_text(json.dumps(manifest,indent=2,allow_nan=False));fields=list(dict.fromkeys(k for r in manifest['pictures'] for k in r))
with (root/'creators.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(manifest['pictures'])
(root/'sources'/'instagram-micro-verified.json').write_text(json.dumps([{k:r[k] for k in ['id','name','reported_audience','post_count','follower_count_source','follower_count_verified_date','recent_activity_verified','biography_source','source_label','age_range']} for r in new],indent=2))
print(json.dumps({'added':len(new),'total':len(manifest['pictures']),'profiles':[(r['name'],r['reported_audience']) for r in new]}))
