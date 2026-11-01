# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import csv,json,os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode,urlsplit,parse_qs
import requests
from bs4 import BeautifulSoup
names='''Kevin Nguyen;Emily Tran;Daniel Le;Anna Pham;Alex Hoang;Michelle Vu;David Chen;Amy Wang;Eric Zhang;Grace Liu;Jason Li;Angela Huang;Ryan Wu;Jessica Lin;Brian Yang;Tiffany Zhou;Andrew Kim;Sarah Park;Daniel Lee;Hannah Choi;Justin Jung;Rachel Kang;Kenji Tanaka;Yuki Sato;Haruka Suzuki;Rina Yamamoto;Ren Nakamura;Hana Kobayashi;Arjun Patel;Priya Shah;Rohan Sharma;Ananya Gupta;Aditya Kumar;Neha Singh;Rahul Mehta;Anjali Rao;Miguel Santos;Isabella Reyes;Paolo Cruz;Andrea Garcia;Carlo Ramos;Sofia Mendoza;Muhammad Rahman;Aisha Khan;Ali Hassan;Fatima Ahmed;Dimas Pratama;Putri Wijaya;Aditya Santoso;Dewi Lestari;Narin Wong;Mali Tan;Wei Lim;Chloe Tan;Marcus Goh;Rachel Teo;Ethan Lau;Natalie Cheung;Justin Chan;Vivian Lam'''.split(';')
rows=[]
for name in names:
 q=f'"{name}" (site:instagram.com OR site:linkedin.com/in/)'
 rows.append({'name_seed':name,'query':q,'google_url':'https://www.google.com/search?'+urlencode({'q':q}),'status':'not_searched'})
path=Path(str(_WORKSPACE_ROOT / 'static/name-search-seeds.csv'))
with path.open('w') as f:
 w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
print('Generated',len(rows),'name combinations:',path)
configured=False
for p in Path('/proc').iterdir():
 if not p.name.isdigit():continue
 try:
  args=(p/'cmdline').read_bytes().split(b'\0')
  if len(args)>1 and args[1]==b'app.py' and str((p/'cwd').resolve())==str(_WORKSPACE_ROOT):
   configured=any(x.startswith(b'SERPER_API_KEY=') and len(x)>15 for x in (p/'environ').read_bytes().split(b'\0'))
 except OSError:pass
print('Running app SERPER_API_KEY configured:',configured)
def trial(row):
 s=requests.Session();s.trust_env=False
 try:
  r=s.get(row['google_url'],headers={'User-Agent':'Mozilla/5.0'},timeout=(5,15))
  soup=BeautifulSoup(r.text,'html.parser');links=[]
  for a in soup.select('a[href]'):
   href=a['href']
   if href.startswith('/url?'):href=parse_qs(urlsplit(href).query).get('q',[''])[0]
   host=(urlsplit(href).hostname or '').lower()
   if host in ('instagram.com','www.instagram.com','linkedin.com','www.linkedin.com'):links.append(href)
  return {'name_seed':row['name_seed'],'http_status':r.status_code,'profile_links':list(dict.fromkeys(links)),'page_text_excerpt':soup.get_text(' ',strip=True)[:300]}
 except requests.RequestException as e:return {'name_seed':row['name_seed'],'error':type(e).__name__}
with ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(trial,rows[:3]))
Path(str(_WORKSPACE_ROOT / 'research/name-google-trials.json')).write_text(json.dumps(results,indent=2))
for result in results:print(json.dumps(result))
