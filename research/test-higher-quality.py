# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,io
from pathlib import Path
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from concurrent.futures import ThreadPoolExecutor
import requests
from PIL import Image
r=json.loads(Path(str(_WORKSPACE_ROOT / 'data/chinese-name-search/results.json')).read_text())['pictures'][1]
u=r['image_url'];p=urlsplit(u)
queries=[('no_resize',urlunsplit(p._replace(query=urlencode([(k,v) for k,v in parse_qsl(p.query) if k!='stp'])))),('s320',urlunsplit(p._replace(query=urlencode([(k,'dst-jpg_s320x320_tt6' if k=='stp' else v) for k,v in parse_qsl(p.query)])))),('public_metadata','https://www.instagram.com/api/v1/users/web_profile_info/?username=amywang.online')]
def test(pair):
 label,url=pair;s=requests.Session();s.trust_env=False
 try:
  response=s.get(url,headers={'User-Agent':'Mozilla/5.0','X-IG-App-ID':'936619743392459'},timeout=(5,15))
  out={'method':label,'status':response.status_code,'bytes':len(response.content)}
  if response.status_code==200:
   if 'json' in response.headers.get('content-type',''):
    data=response.json();user=data.get('data',{}).get('user') or {};out['image_fields']={k:v for k,v in user.items() if 'profile_pic' in k};Path(str(_WORKSPACE_ROOT / 'research/ig-highres-test.json')).write_text(json.dumps(data))
   else:
    try:out['size']=Image.open(io.BytesIO(response.content)).size
    except Exception:pass
  return out
 except Exception as e:return {'method':label,'error':type(e).__name__}
with ThreadPoolExecutor(max_workers=3) as pool:
 for out in pool.map(test,queries):print(json.dumps(out))
