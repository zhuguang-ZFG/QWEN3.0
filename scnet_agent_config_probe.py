import json

import httpx

COOKIE_PATH='/opt/lima-router/reverse_gateway_state/scnet_cookies.json'
BASE='https://www.scnet.cn/acx'
raw=json.load(open(COOKIE_PATH))
cookie='; '.join(f"{c['name']}={c['value']}" for c in raw if c.get('name') and c.get('value'))
headers={'Cookie':cookie,'Origin':'https://www.scnet.cn','Referer':'https://www.scnet.cn/ui/chatbot/','User-Agent':'Mozilla/5.0','Accept':'application/json, text/plain, */*'}
client=httpx.Client(headers=headers, timeout=60)
for path, params in [
('/chatbot/recommend/list', {'enable':'true'}),
('/chatbot/config/list', {}),
('/chatbot/agent/profile/queryAllSwitch', {}),
('/chatbot/agent/profile/queryAllSwitch', {'agent':'research_ai_search'}),
('/chatbot/agent/profile/queryAllSwitch', {'assistant':'read'}),
('/chatbot/agent/profile/mcp/queryTotalSwitch', {'mcpServersType':'sse','chatEnabled':1}),
]:
    r=client.get(BASE+path, params=params)
    try: data=r.json()
    except Exception: data=r.text
    print('\nGET',path,params,r.status_code)
    print(json.dumps(data,ensure_ascii=False,indent=2)[:5000] if not isinstance(data,str) else data[:5000])
