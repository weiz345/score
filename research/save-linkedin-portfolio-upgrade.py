# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,shutil,csv,html
from pathlib import Path
sys.path.insert(0,str(_WORKSPACE_ROOT));from app import DATA,db
root=DATA/'chinese-name-search';static=Path(str(_WORKSPACE_ROOT / 'static'))
report=json.loads((root/'results.json').read_text());target=next(r for r in report['pictures'] if r['profile_url']=='https://www.instagram.com/eatenlau/')
old_filename=target['gallery_filename'];filename='portfolio-ethan-lau-300.jpg'
source=json.loads(Path(str(_WORKSPACE_ROOT / 'research/linkedin-personal-sites.json')).read_text())[1]
url=source['metadata'][0]['content']
shutil.copyfile(str(_WORKSPACE_ROOT / 'research/ethan-lau-portfolio.jpg'),DATA/'images'/filename)
shutil.copyfile(str(_WORKSPACE_ROOT / 'research/ethan-lau-portfolio.jpg'),root/'images'/filename)
old_width,old_height=target['width'],target['height']
target.update(original_image_url=target['image_url'],original_width=old_width,original_height=old_height,original_gallery_filename=old_filename,gallery_filename=filename,filename=filename,width=300,height=300,image_url=url,image_path=str(root/'images'/filename),image_source='https://ethanlausz.com/',linkedin_url='https://www.linkedin.com/in/ethanlau00/',identity_match_basis='Public portfolio explicitly links both this Instagram account and LinkedIn profile; no facial matching')
with db() as con:con.execute('UPDATE pictures SET filename=?,width=?,height=?,image_url=? WHERE profile_url=?',(filename,300,300,url,target['profile_url']))
for path in [root/'results.json',static/'chinese-name-picture-results.json']:path.write_text(json.dumps(report,indent=2))
with (static/'chinese-name-picture-results.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['name_seed','title','profile_url','image_url','gallery_filename','width','height','image_source','linkedin_url','identity_match_basis'],extrasaction='ignore');w.writeheader();w.writerows(report['pictures'])
page=static/'chinese-name-picture-results.html';text=page.read_text().replace('/images/'+old_filename,'/images/'+filename)
needle='<h3>'+html.escape(target['name_seed'])+'</h3>'
# Add provenance only to the upgraded account card.
start=text.index('/images/'+filename);end=text.index('</article>',start)
text=text[:end]+'<p>Upgraded '+str(old_width)+'×'+str(old_height)+' → 300×300 · <a href="https://ethanlausz.com/">Public portfolio source</a> · LinkedIn and Instagram cross-linked</p>'+text[end:]
page.write_text(text)
lrpath=root/'linkedin-higher-quality.json';lr=json.loads(lrpath.read_text())
upgrade={'instagram_url':target['profile_url'],'linkedin_url':target['linkedin_url'],'source_page':target['image_source'],'filename':filename,'width':300,'height':300,'original_width':old_width,'original_height':old_height,'image_url':url,'verification':'Public personal portfolio links both Instagram and LinkedIn; photo sourced from that portfolio'}
lr['verified_matches']=[upgrade];lr['upgraded']=[upgrade];lr['personal_site_checks']=json.loads(Path(str(_WORKSPACE_ROOT / 'research/linkedin-personal-sites.json')).read_text())
for row in lr['results']:
 for c in row['candidates']:
  if c['linkedin_url']==target['linkedin_url']:c['status']='Confirmed through public portfolio linking both accounts; photo from portfolio'
for path in [lrpath,static/'linkedin-higher-quality.json']:path.write_text(json.dumps(lr,indent=2))
page=static/'linkedin-higher-quality.html';text=page.read_text().replace('0 verified public cross-links; 0 larger photos found.','1 match verified through a public portfolio; 1 larger photo found.').replace('No photos compared for identity;','Photos sourced from LinkedIn-linked portfolios are labeled. No photos compared for identity;')
text=text.replace('<h1>LinkedIn photo matching</h1>','<h1>LinkedIn photo matching</h1><article><h2>Upgraded: Ethan Lau / @eatenlau</h2><img src="/images/'+filename+'"><p>'+str(old_width)+'×'+str(old_height)+' → 300×300. <a href="https://ethanlausz.com/">Public portfolio</a> links both his Instagram and LinkedIn. The larger photo comes from his portfolio.</p></article>')
page.write_text(text)
print('Saved verified portfolio upgrade:',old_width,old_height,'to 300 300')
