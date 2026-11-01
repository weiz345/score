# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import urllib.request,urllib.parse,concurrent.futures,json
from pathlib import Path
names=['Tanmay Bakshi','Rishab Jain','Krithik Ramesh','Rishab Gargeya','Anushka Naiknaware','Kavya Kopparapu','Ann Makosinski','Kiara Nirghin','Gitanjali Rao (scientist)','Kritika Singh','Swetha Prabakaran','Shubham Banerjee','Angad Daryani','Arsh Shah Dilbagi','Trisha Prabhu']
def get(name):
 u='https://en.wikipedia.org/w/api.php?'+urllib.parse.urlencode({'action':'query','format':'json','titles':name,'prop':'extracts|pageimages|info','explaintext':1,'piprop':'original','inprop':'url'})
 try:
  data=json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'PublicProfileResearch/1.0'}),timeout=20));page=next(iter(data['query']['pages'].values()));return dict(name=name,page=page)
 except Exception as e:return dict(name=name,error=str(e))
rs=list(concurrent.futures.ThreadPoolExecutor(max_workers=4).map(get,names));Path(str(_WORKSPACE_ROOT / 'research/professional-sources.json')).write_text(json.dumps(rs,indent=2))
for r in rs:
 p=r.get('page',{});print(json.dumps({'name':r['name'],'source':p.get('fullurl'),'photo':p.get('original'),'bio':p.get('extract','')[:12500],'error':r.get('error')}))
