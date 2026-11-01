"""Record a completed visual-review batch by stable numeric contact-sheet index."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'data'/'candidate-rating'
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--batch',type=int,required=True);parser.add_argument('--excluded',default='');args=parser.parse_args()
rows=json.loads((OUT/'index.json').read_text());path=OUT/'review.json';review=json.loads(path.read_text()) if path.exists() else {'eligible_indices':[],'excluded_indices':[],'complete':False,'method':'Manual review of contact sheets: usable single adult portraits only. No face identity matching or ethnicity inference.'}
indices=set(range(args.batch*100,min((args.batch+1)*100,len(rows))));excluded={int(i) for i in args.excluded.split(',') if i};assert excluded<=indices
eligible=(set(review['eligible_indices'])-indices)|(indices-excluded);rejected=(set(review['excluded_indices'])-indices)|excluded
review.update(eligible_indices=sorted(eligible),excluded_indices=sorted(rejected),complete=len(eligible|rejected)==len(rows));temp=path.with_suffix('.tmp');temp.write_text(json.dumps(review,indent=2));temp.replace(path)
print('Reviewed',len(eligible|rejected),'eligible',len(eligible),'excluded',len(rejected),'complete',review['complete'])
