# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import urllib.request,concurrent.futures,json,re
from bs4 import BeautifulSoup
slugs=['steven-he','alan-chikin-chow','ian-boggs','nathan-doan','ricegum','michael-reeves','tenz','iitztimmy','jasontheween','justin-han','zhong']
def fetch(slug):
 url=f'https://www.famousbirthdays.com/people/{slug}.html'
 try:
  raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read().decode()
  soup=BeautifulSoup(raw,'html.parser')
  for x in soup(['script','style','nav','footer']):x.decompose()
  text=soup.get_text(' ',strip=True)
  open(str(_WORKSPACE_ROOT / 'research') + '/'+slug+'.txt','w').write(text)
  return {'slug':slug,'url':url,'text':text[:13500]}
 except Exception as e:return {'slug':slug,'error':str(e)}
results=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(fetch,slugs))
json.dump(results,open(str(_WORKSPACE_ROOT / 'research/sources.json'),'w'),indent=2)
for r in results:print(json.dumps(r))
