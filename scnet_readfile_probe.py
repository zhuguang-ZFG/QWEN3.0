import logging

_log = logging.getLogger(__name__)
import json
import time

import httpx

COOKIE_PATH='/opt/lima-router/reverse_gateway_state/scnet_cookies.json'
BASE='https://www.scnet.cn/acx'
raw=json.load(open(COOKIE_PATH))
cookie='; '.join(f"{c['name']}={c['value']}" for c in raw if c.get('name') and c.get('value'))
headers={'Cookie':cookie,'Origin':'https://www.scnet.cn','Referer':'https://www.scnet.cn/ui/chatbot/','User-Agent':'Mozilla/5.0','Accept':'application/json, text/plain, */*'}
client=httpx.Client(headers=headers, timeout=60, follow_redirects=False)

def dump(label, r):
    try: data=r.json()
    except Exception: data=r.text
    print('\n'+label, r.status_code, json.dumps(data, ensure_ascii=False)[:2000] if not isinstance(data,str) else data[:2000], flush=True)
    return data

name='lima_readfile_probe_'+str(int(time.time()*1000))+'.pdf'
# Minimal valid-ish PDF with text. PDF parser may still parse or reject, but upload/parse protocol is what matters.
needle='SCNET_READFILE_NEEDLE_'+str(int(time.time()*1000))
pdf=(b'%PDF-1.4\n1 0 obj<<>>endobj\n2 0 obj<< /Length 96 >>stream\nBT /F1 12 Tf 72 720 Td (' + needle.encode() + b') Tj ET\nendstream endobj\ntrailer<<>>\n%%EOF\n')
# browser sends totalSize:0 and x-amz-meta-total-size:0 for readFile pdf
r=client.post(BASE+'/chatbot/file/upload/url', json=[{'fileId':'lima-'+str(int(time.time()*1000)), 'fileName':name, 'totalSize':0}])
data=dump('UPLOAD_URL_ARRAY', r)
item=None
if isinstance(data,dict) and isinstance(data.get('data'),list) and data['data']:
    item=data['data'][0]
if not item:
    raise SystemExit('no upload item')
print('ITEM', json.dumps(item, ensure_ascii=False), flush=True)
url=item.get('uploadUrl')
file_name=item.get('fileName') or name
file_id=item.get('fileId')
rr=httpx.put(url, content=pdf, headers={'x-amz-meta-total-size':'0','Content-Type':'application/pdf'}, timeout=60)
print('\nPUT_UPLOAD', rr.status_code, rr.text[:500], flush=True)
for body in [
    {'fileNameList':[file_name]},
    {'fileNameList':[name]},
    {'fileNameList':[file_name], 'fileIdList':[file_id] if file_id else []},
    {'fileName':file_name},
    {'fileNames':[file_name]},
]:
    pr=client.post(BASE+'/chatbot/file/parse', json=body)
    pdata=dump('PARSE '+json.dumps(body,ensure_ascii=False), pr)
    doc_id=None
    try:
        first=pdata['data'][0]
        doc_id=first.get('result') or first.get('documentId') or first.get('id')
    except Exception as exc:
        _log.debug("scnet_readfile_probe: optional dependency or operation failed", exc_info=True)
    if isinstance(pdata,list) and pdata:
        doc_id=pdata[0].get('result') if isinstance(pdata[0],dict) else None
    if doc_id:
        print('DOC_ID', doc_id, flush=True)
        for n in range(8):
            time.sleep(2)
            gr=client.get(BASE+f'/chatbot/file/parse/{doc_id}/progress')
            gdata=dump(f'PROGRESS {n}', gr)
            # try chat payload variants once progress is available enough
            if n in (0,3,7):
                variants=[
                    {'conversationId':'','content':'??????????????? SCNET_READFILE_NEEDLE ???','thinkingEnable':False,'onlineEnable':True,'modelId':520,'textFile':[],'imageFile':[],'autoRun':0,'clusterId':'','documentId':doc_id,'fileName':file_name},
                    {'conversationId':'','content':'??????????????? SCNET_READFILE_NEEDLE ???','thinkingEnable':False,'onlineEnable':True,'modelId':520,'textFile':[],'imageFile':[],'autoRun':0,'clusterId':'','scientificParam':{'documentId':doc_id,'fileName':file_name}},
                    {'conversationId':'','content':'??????????????? SCNET_READFILE_NEEDLE ???','thinkingEnable':False,'onlineEnable':True,'modelId':520,'textFile':[],'imageFile':[],'autoRun':0,'clusterId':'','documentId':doc_id},
                    {'conversationId':'','content':'??????????????? SCNET_READFILE_NEEDLE ???','thinkingEnable':False,'onlineEnable':True,'modelId':520,'textFile':[{'name':file_name,'documentId':doc_id,'type':'application/pdf'}],'imageFile':[],'autoRun':0,'clusterId':''},
                ]
                for idx,payload in enumerate(variants):
                    cr=client.post(BASE+'/chatbot/v1/chat/completion', json=payload, timeout=120)
                    ctext=cr.text[:2000]
                    print('\nCHATVAR', idx, cr.status_code, ctext, flush=True)
