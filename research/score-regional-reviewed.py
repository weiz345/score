"""Score the explicitly reviewed regional batch using the shared cached API client."""
import sys,json,importlib.util,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from run_local import load_local_environment
load_local_environment()
spec=importlib.util.spec_from_file_location('regional_scoring',ROOT/'research'/'discover-bay-area.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.OUT=m.DATA/'regional-qualified';m.OUT.mkdir(exist_ok=True)
if not (m.OUT/'review-index.json').exists():
 fb=json.loads((m.DATA/'bay-area-search'/'review-index.json').read_text());li=json.loads((m.DATA/'west-coast-toronto'/'review-index.json').read_text())
 # Reviewed individually: adult single-person portraits. Group photos, nonportraits,
 # unclear faces, uncertain young subjects and unrelated surname search hits excluded.
 selected=[fb[i] for i in [2,3,7,8,14,15,18]]+li
 for p in selected:
  p.setdefault('region','Bay Area');p.setdefault('platform','Facebook')
 m.write(m.OUT/'review-index.json',selected)
 m.write(m.OUT/'review.json',{'eligible_ids':[p['id'] for p in selected],'review_method':'Manual review of individual portrait images; no face matching or ethnicity inference','initial_review_exclusions':12})
 m.write(m.OUT/'progress.json',dict(m.STATE,stage='review completed',scope='Bay Area; Vancouver BC; Toronto; Los Angeles',surname_queries_planned=58,surname_queries_done=58,profile_candidates=188,location_eligible=69,pictures_checked=128,pictures_available=20,thumbnail_queries_planned=49,thumbnail_queries_done=49))
m.setup_page();m.score(os.environ['ATTRACTIVENESS_API_TOKEN'])
