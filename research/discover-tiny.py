# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
exec(open(str(_WORKSPACE_ROOT / 'research/smaller.py')).read().split('cats=list')[0])
def cat(spec):
 career,country=spec;u=f'https://www.famousbirthdays.com/profession/from/{career}-{country}.html'
 try:
  s=get(u);ls=[]
  for a in s.select('a[href^="/people/"]'):
   t=a.get_text(' ',strip=True);m=re.search(r', (\d+) ',t)
   if m and 20<=int(m[1])<=30:ls.append('https://www.famousbirthdays.com'+a['href'])
  return list(dict.fromkeys(ls))
 except Exception:return []
specs=[('twitchstar',c) for c in ['southkorea','japan','china','taiwan','vietnam','singapore','malaysia','thailand','philippines']]+[('instagramstar',c) for c in ['nepal','hongkong','indonesia','cambodia','mongolia','laos']]
categories=list(concurrent.futures.ThreadPoolExecutor(max_workers=5).map(cat,specs));urls=list(dict.fromkeys(u for us in categories for u in us))
old=json.load(open(base/'smaller-discovery.json'));known={r['url'] for r in old};urls=[u for u in urls if u not in known]
print('Additional public biographies:',len(urls),flush=True)
# Reuse the biography extraction function without running the old discovery batch.
source=open(str(_WORKSPACE_ROOT / 'research/smaller.py')).read();exec(source[source.index('def bio(u):'):source.index('rs=list')])
rs=list(concurrent.futures.ThreadPoolExecutor(max_workers=6).map(bio,urls));(base/'tiny-discovery.json').write_text(json.dumps(rs,indent=2))
for r in rs:
 if r.get('counts') and max(r['counts'])<=100000:
  print(json.dumps({k:v for k,v in r.items() if k!='text'}),flush=True)
