# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import urllib.request,concurrent.futures,json,re
from pathlib import Path
from bs4 import BeautifulSoup
rows=json.load(open(str(_WORKSPACE_ROOT / 'research/instagram-handles.json')))
black={'new','additional','prolific','photoblogging','style','different','photo','profiles','self-titled','selftitled','his','her','their','own'}
rows=[r for r in rows if r['handle'].lower() not in black]
def check(row):
 u='https://www.instagram.com/'+row['handle']+'/'
 try:
  with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'PublicProfileGallery/1.0'}),timeout=12) as response:
   raw=response.read(2500000);final=response.url
  soup=BeautifulSoup(raw,'html.parser');meta={m.get('property') or m.get('name'):m.get('content') for m in soup.select('meta[content]') if (m.get('property') or m.get('name')) in ['og:title','og:image','og:description','description']}
  desc=meta.get('description') or meta.get('og:description') or '';m=re.search(r'([\d,.]+)\s*([KMB]?)\s+Followers',desc,re.I)
  if not m:return dict(row,url=u,metadata=meta,error='No public follower count')
  count=round(float(m[1].replace(',',''))*{'':1,'K':1000,'M':1000000,'B':1000000000}[m[2].upper()]);posts=re.search(r'([\d,]+)\s+Posts',desc,re.I)
  dates=re.findall(r'"(?:taken_at_timestamp|taken_at|datePublished)"\s*:\s*"?(\d{10}|\d{4}-\d{2}-\d{2})',raw.decode(errors='replace'))
  return dict(row,url=u,final=final,metadata=meta,followers=count,posts=int(posts[1].replace(',','')) if posts else None,public_post_dates=dates[:5])
 except Exception as e:return dict(row,url=u,error=str(e))
results=list(concurrent.futures.ThreadPoolExecutor(max_workers=3).map(check,rows));Path(str(_WORKSPACE_ROOT / 'research/micro-instagram-checks.json')).write_text(json.dumps(results,indent=2))
for r in results:
 if 1000<=r.get('followers',0)<=20000:print(json.dumps({k:r.get(k) for k in ['name','handle','followers','posts','public_post_dates','metadata']}))
print('Checked',len(results),'in range',sum(1000<=r.get('followers',0)<=20000 for r in results),'errors',sum('error'in r for r in results))
