# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import urllib.request,concurrent.futures,json
from bs4 import BeautifulSoup
slugs=['fred-liu','elliot-choy','andrew-alexander','kelly-wakasa','luke-eich','edward-zo','justin-phan','brandon-chai','kevin-li','derek-trendz','daniel-oh','eric-pan','eric-ou','edward-park','brandon-choi','justin-tsang','andrew-kim','daniel-simmons','tim-dessaint','ivan-lam','leo-chan']
def fetch(slug):
 url=f'https://www.famousbirthdays.com/people/{slug}.html'
 try:
  raw=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read().decode()
  soup=BeautifulSoup(raw,'html.parser');m=soup.find('meta',property='og:image');img=m.get('content') if m else None
  pics=[{'src':x.get('src'),'alt':x.get('alt')} for x in soup.select('img')][:6]
  for x in soup(['script','style','nav','footer']):x.decompose()
  txt=soup.get_text(' ',strip=True)
  return {'slug':slug,'url':url,'image_url':img,'pics':pics,'text':txt}
 except Exception as e:return {'slug':slug,'error':str(e)}
rs=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(fetch,slugs))
json.dump(rs,open(str(_WORKSPACE_ROOT / 'research/expanded-sources.json'),'w'),indent=2)
for r in rs: print(json.dumps(r))
