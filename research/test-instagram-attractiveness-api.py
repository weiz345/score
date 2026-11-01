# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,hashlib,os
from pathlib import Path
import requests
sys.path.insert(0,str(_WORKSPACE_ROOT));from rank_api import analyze
root=Path(str(_WORKSPACE_ROOT / 'data/chinese-name-search'))
rows=json.loads((root/'results.json').read_text())['pictures']
row=next(r for r in rows if r['profile_url']=='https://www.instagram.com/awakeningwithbrian/')
token=os.environ['ATTRACTIVENESS_API_TOKEN']
image=(Path(str(_WORKSPACE_ROOT / 'data/images'))/row['gallery_filename']).read_bytes()
report={'requested_set':'55 Instagram name-search results','first_profile':row['profile_url'],'service':'api.rate-my-photo.com/attractiveness','scored':[],'stopped':False}
s=requests.Session();s.trust_env=False
try:
 result=analyze(s,image,token)
 report['scored'].append(dict(profile_url=row['profile_url'],image_sha256=hashlib.sha256(image).hexdigest(),**result))
 report['status']='First request succeeded'
except (RuntimeError,ValueError,requests.RequestException) as e:
 report['stopped']=True;report['status']=str(e) if isinstance(e,(RuntimeError,ValueError)) else type(e).__name__
(root/'api-scoring-run.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report))
