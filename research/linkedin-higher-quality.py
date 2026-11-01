# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,re,io,hashlib,html,csv,time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
from urllib.parse import urlsplit,urljoin
import requests
from PIL import Image,ImageOps
from bs4 import BeautifulSoup
sys.path.insert(0,str(_WORKSPACE_ROOT))
from app import fetch,DATA
from profile_search import profile_url
root=DATA/'chinese-name-search';pictures=json.loads((root/'results.json').read_text())['pictures']
key=__import__('os').environ['SERPER_API_KEY']
report_path=root/'linkedin-higher-quality.json'
def search(row):
 handle=urlsplit(row['profile_url']).path.strip('/')
 query=f'"{handle}" site:linkedin.com/in/'
 s=requests.Session();s.trust_env=False
 result={'instagram_url':row['profile_url'],'name_seed':row['name_seed'],'handle':handle,'query':query,'candidates':[]}
 try:
  response=s.post('https://google.serper.dev/search',headers={'X-API-KEY':key},json={'q':query,'num':5},timeout=(5,20))
  if response.status_code!=200:result['error']='Search HTTP '+str(response.status_code);return result
  for item in response.json().get('organic',[])[:5]:
   url=profile_url(item.get('link',''))
   if not url or 'linkedin.com' not in url:continue
   text=item.get('title','')+' '+item.get('snippet','')
   # Retain all search hits for review; direct public-page links establish a match below.
   result['candidates'].append({'linkedin_url':url,'title':item.get('title',''),'snippet':item.get('snippet',''),'handle_in_search_text':bool(re.search(r'(?<![a-z0-9._])'+re.escape(handle)+r'(?![a-z0-9._])',text,re.I)),'status':'Unverified search candidate'})
 except requests.RequestException as e:result['error']=type(e).__name__
 return result
results=[]
with ThreadPoolExecutor(max_workers=4) as pool:
 for i,f in enumerate(as_completed([pool.submit(search,p) for p in pictures]),1):
  results.append(f.result())
  if i%10==0:print(json.dumps({'searched':i,'total':len(pictures),'candidate_links':sum(len(r['candidates']) for r in results)}),flush=True)
results.sort(key=lambda r:r['instagram_url'])
report={'accounts_searched':len(pictures),'results':results,'verified_matches':[],'upgraded':[]}
report_path.write_text(json.dumps(report,indent=2))
print('Search phase complete: '+str(sum(len(r['candidates']) for r in results))+' candidate links',flush=True)
# Verify exact Instagram links on publicly accessible LinkedIn pages. No face comparison.
checks={}
def check(url):
 try:
  body,final=fetch(url,2000000)
  soup=BeautifulSoup(body,'html.parser')
  urls={profile_url(urljoin(final,a['href'])) for a in soup.select('a[href]')}
  # LinkedIn external links may use outbound redirects. Exact Instagram URLs in visible text also count.
  text=soup.get_text(' ',strip=True)
  for found in re.findall(r'https://(?:www\.)?instagram\.com/[A-Za-z0-9._]+/?',text):urls.add(profile_url(found))
  images=[t.get('content') for t in soup.select('meta[property="og:image"],meta[name="twitter:image"]') if t.get('content')]
  return {'public_links':list(u for u in urls if u),'images':images,'final_url':final}
 except Exception as e:return {'error':type(e).__name__}
urls=sorted({c['linkedin_url'] for r in results for c in r['candidates']})
with ThreadPoolExecutor(max_workers=4) as pool:
 for url,checked in zip(urls,pool.map(check,urls)):checks[url]=checked
for r in results:
 for candidate in r['candidates']:
  check_result=checks[candidate['linkedin_url']]
  candidate['public_page_check']=check_result
  if r['instagram_url'] not in check_result.get('public_links',[]):continue
  candidate['status']='Verified public LinkedIn page links to this Instagram profile'
  report['verified_matches'].append({'instagram_url':r['instagram_url'],'linkedin_url':candidate['linkedin_url']})
  original=next(p for p in pictures if p['profile_url']==r['instagram_url'])
  for image_url in check_result.get('images',[]):
   try:
    if 'media.licdn.com' not in (urlsplit(image_url).hostname or ''):continue
    body,resolved=fetch(image_url,10000000)
    with Image.open(io.BytesIO(body)) as im:
     if im.width*im.height>25000000:continue
     im.load();im=ImageOps.exif_transpose(im).convert('RGB')
     if min(im.size)<=min(original['width'],original['height']):continue
     filename='linkedin-'+hashlib.sha256(candidate['linkedin_url'].encode()).hexdigest()[:24]+'.jpg'
     im.save(DATA/'images'/filename,quality=95)
     report['upgraded'].append({'instagram_url':r['instagram_url'],'linkedin_url':candidate['linkedin_url'],'filename':filename,'width':im.width,'height':im.height,'original_width':original['width'],'original_height':original['height'],'image_url':resolved})
     break
   except Exception:continue
report['checks']=checks
report_path.write_text(json.dumps(report,indent=2))
static=Path(str(_WORKSPACE_ROOT / 'static'));(static/'linkedin-higher-quality.json').write_text(json.dumps(report,indent=2))
e=html.escape
parts=['<!doctype html><meta charset="utf-8"><title>LinkedIn photo matching</title><style>body{font:16px system-ui;max-width:1000px;margin:30px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}article{padding:15px;border-bottom:1px solid #52617a}p{line-height:1.6}img{max-width:300px}</style><a href="/static/chinese-name-picture-results.html">Original picture gallery</a><h1>LinkedIn photo matching</h1>',f'<p>{len(pictures)} Instagram accounts searched; {sum(len(r["candidates"]) for r in results)} LinkedIn candidate links; {len(report["verified_matches"])} verified public cross-links; {len(report["upgraded"])} larger photos found. Search candidates remain separate from confirmed matches. No photos compared for identity; no scoring performed.</p>']
for r in results:
 if not r['candidates']:continue
 parts.append('<article><h2>'+e(r['name_seed'])+' / @'+e(r['handle'])+'</h2><a href="'+e(r['instagram_url'],quote=True)+'">Instagram source</a>')
 for c in r['candidates']:parts.append('<p><a href="'+e(c['linkedin_url'],quote=True)+'">'+e(c['title'])+'</a><br>'+e(c['snippet'])+'<br><b>'+e(c['status'])+'</b></p>')
 for u in report['upgraded']:
  if u['instagram_url']==r['instagram_url']:parts.append('<img src="/images/'+e(u['filename'])+'"><p>'+str(u['width'])+'×'+str(u['height'])+'</p>')
 parts.append('</article>')
(static/'linkedin-higher-quality.html').write_text(''.join(parts))
print(json.dumps({'accounts_searched':len(pictures),'candidate_links':sum(len(r['candidates']) for r in results),'unique_linkedin_pages':len(urls),'public_page_failures':sum('error' in c for c in checks.values()),'verified_matches':len(report['verified_matches']),'larger_photos':len(report['upgraded'])}),flush=True)
