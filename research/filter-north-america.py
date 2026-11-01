# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import json,re,time,html,csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit
import requests
DATA=Path(str(_WORKSPACE_ROOT / 'data'));static=Path(str(_WORKSPACE_ROOT / 'static'));root=DATA/'facebook-name-search'
source=json.loads((root/'results.json').read_text());profiles=[p for p in source['profiles'] if p['picture_available']]
key=__import__('os').environ['SERPER_API_KEY']
# Match explicit current-residence statements, not education or photographed landmarks.
na_terms=['united states','usa','u.s.a.','canada','mexico','new york','new jersey','edison','dayton','ohio','sheboygan','wisconsin','fort lauderdale','florida','richmond hill','ontario','vancouver','toronto','montreal','calgary','ottawa','chicago','illinois','boston','massachusetts','san francisco','los angeles','california','seattle','washington','texas','austin','houston','dallas','hawaii','hawai’i','honolulu','puerto rico','guatemala','belize','honduras','el salvador','nicaragua','costa rica','panama','cuba','jamaica','haiti','dominican republic','bahamas','barbados','trinidad','grenada','saint lucia','antigua','dominica','saint kitts','saint vincent','bermuda','greenland']
other_terms=['singapore','philippines','manila','taiwan','taipei','china','shanghai','beijing','hong kong','malaysia','kuala lumpur','thailand','bangkok','japan','tokyo','korea','seoul','indonesia','jakarta','vietnam','hanoi','india','mumbai','london','united kingdom','england','australia','sydney','melbourne','new zealand','auckland','germany','berlin','france','paris','netherlands','amsterdam','brazil','sao paulo']
def classify(text):
 matches=list(re.finditer(r'\bLives in\s+([^;·|\n]+)',text,re.I))
 for m in matches:
  loc=re.split(r'\b(?:Studied|Went to|Former|Works at|Photos|Follow|Single|Married|Joined|Read more|See more|From)\b',m.group(1),maxsplit=1,flags=re.I)[0].strip(' .,;·')[:100]
  low=loc.lower()
  if any(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',low) for t in na_terms):return 'North America',loc
  if any(re.search(r'(?<!\w)'+re.escape(t)+r'(?!\w)',low) for t in other_terms):return 'Other regions',loc
 return 'Unknown',''
def canonical(u):
 p=urlsplit(u);return p.path.rstrip('/').lower() if p.hostname in ['facebook.com','www.facebook.com','m.facebook.com'] else ''
def enrich(p):
 texts=[{'text':p.get('snippet',''),'source_url':p['profile_url'],'evidence_type':'Existing Google-indexed profile snippet'}]
 region,location=classify(p.get('snippet',''))
 if region!='Unknown':return p['profile_url'],dict(region=region,location=location,location_source=p['profile_url'],location_evidence=p['snippet'],location_basis='Public profile explicitly states Lives in; search index may be stale')
 handle=urlsplit(p['profile_url']).path.strip('/')
 q=f'site:facebook.com/{handle} "Lives in"'
 try:
  s=requests.Session();s.trust_env=False;r=s.post('https://google.serper.dev/search',headers={'X-API-KEY':key},json={'q':q,'num':5},timeout=(5,20))
  if r.status_code==200:
   for item in r.json().get('organic',[])[:5]:
    if canonical(item.get('link',''))!=canonical(p['profile_url']):continue
    text=item.get('snippet','');texts.append({'text':text,'source_url':item['link'],'evidence_type':'Targeted Google-indexed profile snippet'})
    region,location=classify(text)
    if region!='Unknown':return p['profile_url'],dict(region=region,location=location,location_source=item['link'],location_evidence=text,location_basis='Public profile explicitly states Lives in; search index may be stale')
 except requests.RequestException:pass
 return p['profile_url'],dict(region='Unknown',location='',location_source=p['profile_url'],location_evidence='',location_basis='No explicit supported current location found; education and photo backgrounds were not used')
locations={}
with ThreadPoolExecutor(max_workers=4) as pool:
 for i,f in enumerate(as_completed([pool.submit(enrich,p) for p in profiles]),1):
  url,location=f.result();locations[url]=location
  if i%10==0:print('Location checks '+str(i)+'/'+str(len(profiles)),flush=True)
(root/'location-evidence.json').write_text(json.dumps(locations,indent=2))
for p in source['profiles']:
 if p['profile_url'] in locations:p.update(locations[p['profile_url']])
for path in [root/'results.json',static/'facebook-name-results.json']:path.write_text(json.dumps(source,indent=2))
ranked=json.loads((root/'api-rankings.json').read_text())
for p in ranked['pictures']:p.update(locations.get(p['profile_url'],{'region':'Unknown','location':''}))
for path in [root/'api-rankings.json',static/'facebook-api-rankings.json']:path.write_text(json.dumps(ranked,indent=2))
with (static/'facebook-api-rankings.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['rank','name_seed','profile_url','score','score_adjusted','region','location','location_source','location_evidence','width','height','api_version'],extrasaction='ignore');w.writeheader();w.writerows(ranked['pictures'])
# Add a region filter to both pages, retaining full original score ranks.
for filename,is_ranked in [('facebook-ranked.html',True),('facebook-name-results.html',False)]:
 path=static/filename;text=path.read_text()
 text=re.sub(r'<div id="region-filter-panel">[\s\S]*?</div>','',text)
 panel='<div id="region-filter-panel"><p><label>Location <select id="region-filter"><option value="all">All locations</option><option value="North America">North America</option><option value="Other regions">Other regions</option><option value="Unknown">Unknown location</option></select></label> <span id="region-count"></span></p><p>Based on public Lives in statements. Includes the US, Canada, Mexico, Central America and the Caribbean. Unknown locations are excluded from the North America filter. Search-indexed location information may be stale.</p></div>'
 text=text.replace('<div class="grid">',panel+'<div class="grid">',1)
 def annotate(m):
  article=m.group(0)
  match=next((p for p in profiles if html.escape(p['profile_url'],quote=True) in article),None)
  if match is None:return article
  loc=locations[match['profile_url']];region=loc['region']
  article=article.replace('<article>','<article data-region="'+html.escape(region,quote=True)+'">',1)
  info='<p class="location-label">'+html.escape(loc['location'] or 'Location unknown')
  if loc['location_evidence']:info+=' · <a title="'+html.escape(loc['location_evidence'],quote=True)+'" href="'+html.escape(loc['location_source'],quote=True)+'">Location source</a>'
  return article.replace('</article>',info+'</p></article>')
 text=re.sub(r'<article>[\s\S]*?</article>',annotate,text)
 script="""<script id="region-filter-script">const regionSelect=document.getElementById('region-filter');function filterRegion(){const cards=[...document.querySelectorAll('.grid article')];let shown=0;for(const card of cards){card.hidden=regionSelect.value!=='all'&&card.dataset.region!==regionSelect.value;if(!card.hidden)shown++;}document.getElementById('region-count').textContent=shown+' of '+cards.length+' profiles';const url=new URL(location.href);url.searchParams.set('region',regionSelect.value);history.replaceState(null,'',url);}const initialRegion=new URLSearchParams(location.search).get('region');if([...regionSelect.options].some(o=>o.value===initialRegion))regionSelect.value=initialRegion;regionSelect.addEventListener('change',filterRegion);filterRegion();</script>"""
 text=re.sub(r'<script id="region-filter-script">[\s\S]*?</script>','',text)+script
 path.write_text(text)
print(json.dumps({'all_photos':{region:sum(l['region']==region for l in locations.values()) for region in ['North America','Other regions','Unknown']},'ranked_photos':{region:sum(p['region']==region for p in ranked['pictures']) for region in ['North America','Other regions','Unknown']}}),flush=True)
