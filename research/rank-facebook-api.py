# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import sys,json,hashlib,time,html,csv,io
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import requests
sys.path.insert(0,str(_WORKSPACE_ROOT))
from rank_api import analyze
DATA=Path(str(_WORKSPACE_ROOT / 'data'));root=DATA/'facebook-name-search';static=Path(str(_WORKSPACE_ROOT / 'static'))
ELIGIBLE={0,2,3,4,5,7,14,17,18,19,20,22,23,24,25}
EXCLUDED={1:'Multiple people in the photo',6:'Illustration',8:'Illustration',9:'Face too small for this scoring batch',10:'Flowers; no portrait',11:'Historical portrait with uncertain age and identity',12:'Face hidden',13:'Eyes covered by sunglasses',15:'Face too small for this scoring batch',16:'Photo within a photo with multiple people',21:'Face masked',26:'Face too small in an edited image'}
def main(token):
 rows=[p for p in json.loads((root/'results.json').read_text())['profiles'] if p['picture_available']]
 cache_path=DATA/'service'/'cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 first=json.loads((root/'api-scoring-run.json').read_text())
 previous=first.get('scored',[])
 chosen=[]
 for i,p in enumerate(rows):
  if i not in ELIGIBLE:continue
  p=dict(p);image=(DATA/'images'/p['filename']).read_bytes()
  p['cache_key']='facebook:'+hashlib.sha256(p['profile_url'].encode()).hexdigest()[:24]+':'+hashlib.sha256(image).hexdigest()
  for prev in previous:
   if prev['profile_url']==p['profile_url']:
    cache[p['cache_key']]={k:prev[k] for k in ['score','score_adjusted','api_version']}
  chosen.append((p,image))
 results=[];errors=[];timings=[];stopped=False;started=time.perf_counter()
 def save():
  ordered=sorted(results,key=lambda p:(-p['score'],p['profile_url']))
  for rank,p in enumerate(ordered,1):p['rank']=rank
  report={'service':'api.rate-my-photo.com/attractiveness','pictures':ordered,'score_max':10,'ranking_by':'raw API score','eligible':len(chosen),'source_picture_count':len(rows),'excluded':[dict(profile_url=p['profile_url'],reason=EXCLUDED.get(i,'Not selected')) for i,p in enumerate(rows) if i not in ELIGIBLE],'errors':errors,'request_durations_seconds':timings,'elapsed_seconds':round(time.perf_counter()-started,2),'concurrency':3,'stopped':stopped,'complete':len(results)+len(errors)==len(chosen),'note':'Subjective third-party estimates, not validated on these photos. Ages and identities not independently verified. No ethnicity inferred.'}
  for path in [root/'api-rankings.json',static/'facebook-api-rankings.json']:
   temp=path.with_suffix('.tmp');temp.write_text(json.dumps(report,indent=2));temp.replace(path)
  temp=cache_path.with_suffix('.tmp');temp.write_text(json.dumps(cache,indent=2));temp.replace(cache_path)
  with (static/'facebook-api-rankings.csv').open('w') as f:
   w=csv.DictWriter(f,fieldnames=['rank','name_seed','profile_url','score','score_adjusted','width','height','api_version'],extrasaction='ignore');w.writeheader();w.writerows(ordered)
  e=html.escape
  parts=['<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Facebook API scores</title><style>body{font:16px system-ui;max-width:1100px;margin:30px auto;padding:20px;background:#101522;color:#edf2fa}a{color:#9cd8c4}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:18px}article{padding:16px;background:#1c2638;border-radius:12px;overflow-wrap:anywhere}img{width:100%;aspect-ratio:1;object-fit:contain}.score{font-size:24px;font-weight:bold}p{line-height:1.5}</style><a href="/static/facebook-name-results.html">All Facebook pictures</a> · <a href="/static/chinese-name-picture-results.html">Instagram pictures</a><h1>Facebook · attractiveness API scores</h1>',f'<p>{len(ordered)} of {len(chosen)} selected portraits scored. {len(rows)-len(chosen)} nonportraits or unsuitable photos excluded. Ordered by raw API score; adjusted scores shown separately. No validation on this dataset. Ages and identities not independently verified.</p><p>'+('Stopped after an API error; successful results saved.' if stopped else 'Batch complete.' if report['complete'] else 'Scoring in progress; refresh for results.')+'</p><a href="/static/facebook-api-rankings.csv">Download scores CSV</a><div class="grid">']
  for p in ordered:parts.append('<article><img loading="lazy" alt="Public Facebook profile image" src="/images/'+e(p['filename'])+'"><div class="score">#'+str(p['rank'])+' · '+format(p['score'],'.2f')+' / 10</div><h3>'+e(p['name_seed'])+'</h3><p>Adjusted API score: '+format(p['score_adjusted'],'.2f')+' / 10</p><a href="'+e(p['profile_url'],quote=True)+'">'+e(p['title'])+'</a></article>')
  parts.append('</div><details><summary>Excluded photos and service errors</summary>')
  for p in report['excluded']:parts.append('<p>'+e(p['profile_url'])+' — '+e(p['reason'])+'</p>')
  for p in errors:parts.append('<p>'+e(p['profile_url'])+' — '+e(p['error'])+'</p>')
  parts.append('</details>');(static/'facebook-ranked.html').write_text(''.join(parts))
 def work(item):
  p,image=item;begin=time.perf_counter()
  try:
   s=requests.Session();s.trust_env=False;score=analyze(s,image,token)
   return p,score,None,round(time.perf_counter()-begin,3)
  except (RuntimeError,ValueError,requests.RequestException) as exc:
   return p,None,str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__,round(time.perf_counter()-begin,3)
 pending=[]
 for p,image in chosen:
  if p['cache_key'] in cache:results.append(dict(p,**cache[p['cache_key']]))
  else:pending.append((p,image))
 save();iterator=iter(pending)
 with ThreadPoolExecutor(max_workers=3) as pool:
  running={pool.submit(work,item) for item in [next(iterator,None) for _ in range(3)] if item is not None}
  while running:
   done,running=wait(running,return_when=FIRST_COMPLETED)
   for f in done:
    p,score,error,duration=f.result();timings.append(duration)
    if error:
     errors.append({'profile_url':p['profile_url'],'error':error,'duration_seconds':duration})
     if 'HTTP 400;' not in error and 'HTTP 422;' not in error:stopped=True
    else:
     cache[p['cache_key']]=score;results.append(dict(p,**score))
    save();print(json.dumps({'scored':len(results),'eligible':len(chosen),'duration_seconds':duration,'error':error,'stopped':stopped}),flush=True)
   if not stopped:
    while len(running)<3:
     item=next(iterator,None)
     if item is None:break
     running.add(pool.submit(work,item))
 save()
 summary={'scored':len(results),'eligible':len(chosen),'excluded':len(rows)-len(chosen),'errors':len(errors),'stopped':stopped,'elapsed_seconds':round(time.perf_counter()-started,2),'request_durations_seconds':timings}
 print(json.dumps(summary),flush=True)

if __name__ == "__main__":
    main(__import__("os").environ["ATTRACTIVENESS_API_TOKEN"])
