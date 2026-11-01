"""Score reviewed adult candidate portraits, deduplicating image bytes and caching results."""
import argparse,csv,hashlib,json,os,re,sys,time,threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,wait,FIRST_COMPLETED
import requests
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app import DATA
from rank_api import analyze
from run_local import load_local_environment
OUT=DATA/'candidate-rating';OUT.mkdir(exist_ok=True);STATIC=ROOT/'static';LOCAL=threading.local()
def atomic(path,data):
 temp=path.with_suffix('.tmp');temp.write_text(json.dumps(data,indent=2));temp.replace(path)
def main(follow):
 (STATIC/'candidate-ratings.html').write_text((ROOT/'templates'/'candidate-ratings.html').read_text())
 load_local_environment();token=os.environ['ATTRACTIVENESS_API_TOKEN'];started=time.perf_counter()
 rows=json.loads((OUT/'index.json').read_text());cache_path=DATA/'service'/'cache.json';cache=json.loads(cache_path.read_text()) if cache_path.exists() else {}
 scores={}
 for key,val in cache.items():
  digest=key.rsplit(':',1)[-1]
  if re.fullmatch('[0-9a-f]{64}',digest):scores[digest]=val
 hashes={p['id']:hashlib.sha256((DATA/'images'/p['filename']).read_bytes()).hexdigest() for p in rows}
 failures={};attempted=set();durations=[];api_calls=0;cache_hits=set();stopped=False;stop_reason='';review={};last_publish=0
 existing=OUT/'image-errors.json'
 if existing.exists():failures=json.loads(existing.read_text())
 def read_review():return json.loads((OUT/'review.json').read_text()) if (OUT/'review.json').exists() else {'eligible_indices':[],'excluded_indices':[],'complete':False}
 def publish(force=False):
  nonlocal last_publish
  now=time.perf_counter()
  if not force and now-last_publish<2:return
  last_publish=now;web=[];ranked=[];eligible=set(review.get('eligible_indices',[]));excluded=set(review.get('excluded_indices',[]))
  for i,p in enumerate(rows):
   row={k:p[k] for k in ['id','title','platform','profile_url','filename','width','height','queried_regions','location_status']};digest=hashes[p['id']]
   if i in eligible and digest in scores:row.update(scores[digest],status='scored');ranked.append(row)
   elif i in excluded:row.update(status='excluded',reason='Not a usable single adult portrait, or age/face too uncertain')
   elif i in eligible and digest in failures:row.update(status='api_error',reason=failures[digest]['error'])
   elif i in eligible:row.update(status='waiting_for_score',reason='Reviewed; waiting for API')
   else:row.update(status='awaiting_review',reason='Portrait eligibility review pending')
   web.append(row)
  ranked.sort(key=lambda p:(-p['score'],p['id']))
  for rank,p in enumerate(ranked,1):p['rank']=rank
  web.sort(key=lambda p:(0,-p['score'],p['id']) if p['status']=='scored' else (1,p['title'].lower(),p['id']))
  above=sum(p['score']>7 for p in ranked);waiting=sum(i in eligible and hashes[p['id']] not in scores and hashes[p['id']] not in failures for i,p in enumerate(rows))
  stage='stopped on API error' if stopped else 'complete' if review.get('complete') and waiting==0 and not running else 'rating and reviewing'
  state={'stage':stage,'total_candidates':len(rows),'reviewed':len(eligible|excluded),'eligible_reviewed':len(eligible),'excluded':len(excluded),'scored':len(ranked),'above_7':above,'above_7_percentage':round(100*above/len(ranked),2) if ranked else None,'accounts_with_api_errors':sum(p['status']=='api_error' for p in web),'api_calls_this_run':api_calls,'duplicate_images_reused':max(0,len(ranked)-len({hashes[p['id']] for p in ranked})),'concurrency':3,'mean_call_seconds':round(sum(durations)/len(durations),3) if durations else None,'elapsed_seconds':round(now-started,1),'stop_reason':stop_reason,'note':'API scores rate these images, not verified account identities. Images and query regions may be stale; photos vary in resolution and quality. Names do not establish ethnicity.'}
  atomic(OUT/'progress.json',state);atomic(STATIC/'candidate-rating-progress.json',state);atomic(OUT/'results.json',web);atomic(STATIC/'candidate-rating-results.json',web);atomic(OUT/'image-errors.json',failures)
  if force:
   fields=['rank','id','title','platform','profile_url','score','score_adjusted','status','reason','filename','width','height','queried_regions','location_status']
   temp=STATIC/'candidate-rating-results.csv.tmp'
   with temp.open('w',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader();writer.writerows(web)
   temp.replace(STATIC/'candidate-rating-results.csv')
   print(json.dumps(state),flush=True)
 def worker(digest,row):
  start=time.perf_counter()
  try:
   if not hasattr(LOCAL,'session'):LOCAL.session=requests.Session();LOCAL.session.trust_env=False
   result=analyze(LOCAL.session,(DATA/'images'/row['filename']).read_bytes(),token)
   return digest,result,None,round(time.perf_counter()-start,3)
  except (RuntimeError,ValueError,requests.RequestException) as exc:return digest,None,str(exc) if isinstance(exc,(RuntimeError,ValueError)) else type(exc).__name__,round(time.perf_counter()-start,3)
 running={}
 with ThreadPoolExecutor(max_workers=3) as pool:
  while True:
   review=read_review();eligible=set(review.get('eligible_indices',[]));pending=[];seen=set(running.values())
   for i,p in enumerate(rows):
    digest=hashes[p['id']]
    if i in eligible and digest in scores:cache_hits.add(digest)
    if i in eligible and digest not in scores and digest not in failures and digest not in seen and digest not in attempted:pending.append((digest,p));seen.add(digest)
   if not stopped:
    for digest,p in pending[:max(0,3-len(running))]:running[pool.submit(worker,digest,p)]=digest;attempted.add(digest);api_calls+=1
   if running:
    done,_=wait(running,timeout=.5,return_when=FIRST_COMPLETED)
    for f in done:
     running.pop(f);digest,result,error,duration=f.result();durations.append(duration)
     if error:
      failures[digest]={'error':error,'seconds':duration}
      if 'HTTP 400;' not in error and 'HTTP 422;' not in error:stopped=True;stop_reason=error
     else:scores[digest]=result;cache['image:'+digest]=result;atomic(cache_path,cache)
   publish()
   if stopped and not running:break
   if not running and not pending:
    if review.get('complete') or not follow:break
    time.sleep(.5)
  publish(force=True)
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--follow-review',action='store_true');args=parser.parse_args();main(args.follow_review)
