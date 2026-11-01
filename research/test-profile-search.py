# Resolve this checkout without depending on the original container paths.
_WORKSPACE_ROOT = __import__('pathlib').Path(__file__).resolve().parents[1]
import io,json,os,sys,tempfile
from pathlib import Path
from unittest.mock import patch,Mock
from PIL import Image
sys.path.insert(0,str(_WORKSPACE_ROOT))
with tempfile.TemporaryDirectory() as directory:
 os.environ['GALLERY_DATA']=directory
 import app,profile_search
 client=app.app.test_client()
 assert profile_search.profile_url('https://www.instagram.com/alice/?ref=x')=='https://www.instagram.com/alice/'
 for url in ['https://instagram.com/p/abc/','https://instagram.com/reels/','https://linkedin.com/company/example/','https://evilinstagram.com/alice/','https://user:pass@instagram.com/alice/']:
  assert profile_search.profile_url(url) is None,url
 with patch.dict(os.environ,{},clear=True),patch.object(profile_search.requests,'post') as request:
  assert client.post('/api/profile-search',json={'query':'person'}).status_code==503
  request.assert_not_called()
 assert client.post('/api/profile-search',json={'query':''}).status_code==400
 response=Mock(status_code=200);response.json.return_value={'organic':[{'title':'Alice','link':'https://www.instagram.com/Alice/?foo=bar'},{'title':'Biography','link':'https://example.com/about'},{'title':'Bad link','link':'http://127.0.0.1/private'}]}
 def source_fetch(url,limit):
  if url.startswith('http://127.'):raise ValueError('Private address')
  return b'<h1>Alice Example</h1><a href="https://instagram.com/alice/">Instagram</a><a href="https://www.linkedin.com/in/alice-example/">LinkedIn</a><a href="https://www.instagram.com/p/123/">Post</a>',url
 with patch.dict(os.environ,{'SERPER_API_KEY':'mock-only'}),patch.object(profile_search.requests,'post',return_value=response) as request,patch.object(app,'fetch',side_effect=source_fetch):
  result=client.post('/api/profile-search',json={'query':'Alice Example photographer'});assert result.status_code==200,result.json
  data=result.json;assert len(data['profiles'])==2 and len(data['page_errors'])==1
  assert request.call_count==1 and request.call_args.kwargs['json']['num']==10
  batch=data['batch_id'];assert (Path(directory)/'search'/(batch+'.json')).exists()
 image=io.BytesIO();Image.new('RGB',(12,12),'blue').save(image,format='JPEG')
 def media_fetch(url,limit):
  if url.startswith('https://images.example.com'):return image.getvalue(),url
  return b'<meta property="og:image" content="https://images.example.com/portrait.jpg">',url
 with patch.object(app,'validate'),patch.object(app,'fetch',side_effect=media_fetch) as request:
  result=client.post('/api/profile-search/import',json={'batch_id':batch,'indices':[0,1,0]});assert result.status_code==200
  assert len(result.json['results'])==2 and all(r['ok'] for r in result.json['results'])
  calls=request.call_count
  repeated=client.post('/api/profile-search/import',json={'batch_id':batch,'indices':[0,1]});assert all(r['reused'] for r in repeated.json['results']) and request.call_count==calls
  assert client.get('/api/pictures').json['total']==2
 assert client.post('/api/profile-search/import',json={'batch_id':'../bad','indices':[0]}).status_code==400
 assert client.post('/api/profile-search/import',json={'batch_id':batch,'indices':[True]}).status_code==400
 assert client.post('/api/profile-search',json={'query':'test'},headers={'Origin':'https://unrelated.example'}).status_code==403
 with patch.dict(os.environ,{'SERPER_API_KEY':'mock-only'}),patch.object(profile_search.requests,'post',return_value=Mock(status_code=402)):
  error=client.post('/api/profile-search',json={'query':'test'});assert error.status_code==502 and 'mock-only' not in error.get_data(as_text=True)
 print('PASS: canonical profile links, missing-key handling, bounded mocked search, public-link extraction, provenance, imports, duplicate reuse, invalid inputs, same-origin checks and provider failures.')
