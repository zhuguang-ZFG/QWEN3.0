import json, time
import httpx
COOKIE_PATH='/opt/lima-router/reverse_gateway_state/scnet_cookies.json'
BASE='https://www.scnet.cn/acx'
raw=json.load(open(COOKIE_PATH))
cookie='; '.join(f"{c['name']}={c['value']}" for c in raw if c.get('name') and c.get('value'))
headers={'Cookie':cookie,'Origin':'https://www.scnet.cn','Referer':'https://www.scnet.cn/ui/chatbot/','User-Agent':'Mozilla/5.0','Accept':'application/json, text/plain, */*'}
client=httpx.Client(headers=headers, timeout=30, follow_redirects=False)

def safe(obj):
    s=json.dumps(obj, ensure_ascii=False) if not isinstance(obj,str) else obj
    return s[:1200]

def post(path, body):
    try:
        r=client.post(BASE+path, json=body)
        try: data=r.json()
        except Exception: data=r.text
        print('\nPOST',path,'body',safe(body),'->',r.status_code,safe(data), flush=True)
        return r.status_code,data
    except Exception as e:
        print('\nPOST',path,'ERR',repr(e), flush=True)
        return None,None

def get(path, params=None):
    try:
        r=client.get(BASE+path, params=params)
        try: data=r.json()
        except Exception: data=r.text
        print('\nGET',path,'params',safe(params or {}),'->',r.status_code,safe(data), flush=True)
        return r.status_code,data
    except Exception as e:
        print('\nGET',path,'ERR',repr(e), flush=True)
        return None,None

name='lima_probe_'+str(int(time.time()*1000))+'.txt'
content=b'hello parse probe\nNEEDLE=SCNET_PARSE_PROBE\n'
size=len(content)
variants=[
 {'fileName':name,'fileSize':size,'contentType':'text/plain'},
 {'name':name,'size':size,'type':'text/plain'},
 {'fileName':name,'size':size,'type':'text/plain'},
 {'filename':name,'size':size,'mimeType':'text/plain'},
 {'fileName':name,'fileType':'txt','size':size},
]
results=[]
for v in variants:
    st,data=post('/chatbot/file/upload/url', v)
    results.append((v,data))

st,sig=get('/chatbot/file/sso/form/signature')
oss_url=None
if isinstance(sig,dict) and isinstance(sig.get('data'),dict):
    d=sig['data']; host=d['host'].rstrip('/'); key=d['dir'].strip('/')+'/'+name
    form={'key':key,'policy':d['policy'],'OSSAccessKeyId':d['accessid'],'success_action_status':'200','signature':d['signature']}
    if d.get('accessControl'): form['x-oss-object-acl']=d['accessControl']
    rr=httpx.post(host+'/', data=form, files={'file':(name,content,'text/plain')}, timeout=30)
    print('\nOSS_UPLOAD',rr.status_code,rr.text[:200], flush=True)
    oss_url=host+'/'+key
    print('OSS_URL',oss_url, flush=True)

parse_candidates=[]
if oss_url:
    parse_candidates += [
      {'name':name,'path':oss_url,'size':size,'type':'text/plain'},
      {'fileName':name,'fileUrl':oss_url,'fileSize':size,'fileType':'txt'},
      {'url':oss_url,'fileName':name,'size':size,'type':'text/plain'},
      {'files':[{'name':name,'path':oss_url,'size':size,'type':'text/plain'}]},
      {'textFile':[{'name':name,'path':oss_url,'size':size,'type':'text/plain'}]},
      {'fileList':[{'name':name,'path':oss_url,'size':size,'type':'text/plain'}]},
      {'sourceUrl':oss_url,'name':name},
      {'ossUrl':oss_url,'name':name,'type':'txt'},
    ]
for original,result in results:
    if isinstance(result,dict):
        d=result.get('data')
        if isinstance(d,dict):
            parse_candidates += [d, {'fileName':d.get('fileName') or name,'fileId':d.get('fileId'),'path':d.get('url') or d.get('path') or d.get('uploadUrl'),'size':size,'type':'text/plain'}]

for c in parse_candidates:
    post('/chatbot/file/parse', c)
    fid = c.get('fileId') or c.get('id') if isinstance(c,dict) else None
    if fid: get(f'/chatbot/file/parse/{fid}/progress')

for params in [
 {'content':'hello','modelId':520},
 {'query':'hello','modelId':520},
 {'documentId':'','datasetId':'','content':'hello'},
 {'fileName':name,'fileUrl':oss_url or '', 'modelId':520},
]:
    get('/chatbot/v1/agent/paper', params)
