# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import urllib.request,concurrent.futures,json,re
from bs4 import BeautifulSoup
from pathlib import Path
base=Path(str(_WORKSPACE_ROOT / 'research'));headers={'User-Agent':'Mozilla/5.0'}
def get(u):return BeautifulSoup(urllib.request.urlopen(urllib.request.Request(u,headers=headers),timeout=20).read(),'html.parser')
def category(country):
 u=f'https://www.famousbirthdays.com/profession/from/instagramstar-{country}.html'
 try:
  s=get(u);ls=[]
  for a in s.select('a[href^="/people/"]'):
   t=a.get_text(' ',strip=True);m=re.search(r', (\d+) Instagram',t)
   if m and 20<=int(m[1])<=30:ls.append('https://www.famousbirthdays.com'+a['href'])
  return country,list(dict.fromkeys(ls))
 except Exception as e:return country,[]
cats=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(category,['southkorea','japan','china','taiwan','vietnam','singapore','malaysia','thailand','philippines']))
urls=list(dict.fromkeys(u for _,us in cats for u in us));print('Candidates',len(urls),flush=True)
def bio(u):
 try:
  s=get(u);title=s.title.get_text().split(' - ')[0];og=s.find('meta',property='og:image')
  for x in s(['script','style','nav','footer']):x.decompose()
  t=s.get_text(' ',strip=True);about=t.split(' About ',1)[-1].split(' Popularity ',1)[0]
  matches=list(re.finditer(r'([\d,]+(?:\.\d+)?)\s*(million|[kK])?\s*(?:(?:dedicated|Instagram|TikTok|YouTube)\s+)*(?:followers|subscribers|fans)',about))
  counts=[]
  for m in matches:
   n=float(m[1].replace(',',''));unit=m[2] or '';n=n*1000000 if unit=='million' else n*1000 if unit.lower()=='k' else n
   counts.append(int(n))
  return dict(name=title,url=u,image_url=og.get('content') if og else None,text=t,counts=counts)
 except Exception as e:return dict(url=u,error=str(e))
rs=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(bio,urls))
(base/'smaller-discovery.json').write_text(json.dumps(rs,indent=2))
for r in rs:
 if any(10000<=n<=500000 for n in r.get('counts',[])) and re.search(r'\b(He|His| he | his )',r.get('text','')):
  print(json.dumps(r),flush=True)
