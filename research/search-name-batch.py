# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,csv,json,html,time,unicodedata
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import requests
sys.path.insert(0,str(_WORKSPACE_ROOT))
from profile_search import profile_url
key=__import__('os').environ['SERPER_API_KEY']
root=Path(str(_WORKSPACE_ROOT / 'static'))
seeds=list(csv.DictReader((root/'name-search-seeds.csv').open()))
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKD',s).lower() if c.isalnum() or c.isspace())
def run(pair):
 i,row=pair
 if i==0 and (_WORKSPACE_ROOT/'research'/'serper-first-result.json').exists(): data=json.loads(Path(str(_WORKSPACE_ROOT / 'research/serper-first-result.json')).read_text())
 else:
  session=requests.Session();session.trust_env=False
  try:
   r=session.post('https://google.serper.dev/search',headers={'X-API-KEY':key},json={'q':row['query'],'num':5},timeout=(5,20))
   if r.status_code!=200:return {'name':row['name_seed'],'error':'HTTP '+str(r.status_code),'profiles':[]}
   data=r.json()
  except requests.RequestException:return {'name':row['name_seed'],'error':'Search request failed','profiles':[]}
 matches=[]
 for item in data.get('organic',[])[:5]:
  url=profile_url(item.get('link',''))
  if not url:continue
  text=item.get('title','')+' '+item.get('snippet','')
  tokens=norm(text).split()
  name_match=all(t in tokens for t in norm(row['name_seed']).split())
  matches.append({'profile_url':url,'title':item.get('title',''),'snippet':item.get('snippet',''),'name_in_search_text':name_match,'verification':'Google-indexed profile link; current account identity and demographics not verified'})
 return {'name':row['name_seed'],'query':row['query'],'google_url':row['google_url'],'profiles':matches}
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for future in as_completed([pool.submit(run,p) for p in enumerate(seeds)]):results.append(future.result())
results.sort(key=lambda r:r['name'])
(root/'name-search-results.json').write_text(json.dumps(results,indent=2))
profiles=[dict(name_seed=r['name'],**p) for r in results for p in r['profiles']]
with (root/'name-search-results.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=['name_seed','profile_url','title','snippet','name_in_search_text','verification']);w.writeheader();w.writerows(profiles)
e=html.escape
parts=['<!doctype html><meta charset="utf-8"><title>Name search results</title><style>body{font:16px system-ui;max-width:1000px;margin:35px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}article{padding:16px;border-bottom:1px solid #52617a}p{line-height:1.5}</style><a href="/search">Search and import pictures</a> · <a href="/dataset?set=small-creators">All saved profiles</a><h1>Name search results</h1>',f'<p>{len(seeds)} name queries; {len(profiles)} profile links across {sum(bool(r["profiles"]) for r in results)} names. Names are search seeds, not evidence of ethnicity. Links are confirmed in Google results; account identity, age, follower count and current availability are not verified. No pictures imported or scored.</p><a href="/static/name-search-results.csv">Download CSV</a>']
for r in results:
 parts.append('<article><h2>'+e(r['name'])+'</h2>')
 if r.get('error'):parts.append('<p>'+e(r['error'])+'</p>')
 if not r['profiles']:parts.append('<p>No profile links found.</p>')
 for p in r['profiles']:
  parts.append('<p><a target="_blank" rel="noopener noreferrer" href="'+e(p['profile_url'],quote=True)+'">'+e(p['title'])+'</a><br>'+e(p['profile_url'])+'<br>'+e(p['snippet'])+'<br><small>'+('Name appears in search text' if p['name_in_search_text'] else 'Name match needs review')+'</small></p>')
 parts.append('</article>')
(root/'name-search-results.html').write_text(''.join(parts))
print(json.dumps({'queries':len(seeds),'profile_links':len(profiles),'unique_profiles':len(set(p['profile_url'] for p in profiles)),'names_with_links':sum(bool(r['profiles']) for r in results),'name_matches':sum(p['name_in_search_text'] for p in profiles),'errors':sum('error' in r for r in results)}))
