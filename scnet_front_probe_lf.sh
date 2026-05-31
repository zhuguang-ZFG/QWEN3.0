set -e
cd /tmp
rm -rf scnet_front
mkdir scnet_front
cd scnet_front
python3 - <<'PY'
import re, urllib.request, pathlib
base='https://www.scnet.cn'
html=urllib.request.urlopen(base+'/ui/chatbot/', timeout=20).read().decode('utf-8','ignore')
pathlib.Path('index.html').write_text(html, encoding='utf-8')
urls=set(re.findall(r'(?:src|href)="([^"]+\.(?:js|css)[^"]*)"', html))
print('assets', len(urls))
for url in sorted(urls):
    full=url if url.startswith('http') else base+url
    name=re.sub(r'[^A-Za-z0-9._-]+','_',url).strip('_')[-180:]
    try:
        data=urllib.request.urlopen(full, timeout=30).read()
        pathlib.Path(name).write_bytes(data)
    except Exception as exc:
        print('fail', full, exc)
PY
python3 - <<'PY'
from pathlib import Path
terms=['file/upload/url','file/parse','textFile','imageFile','fileId','uploadUrl','download/url','onlineEnable','mcpEnable']
for path in Path('.').glob('*.js'):
    text=path.read_text(encoding='utf-8', errors='ignore')
    hits=[term for term in terms if term in text]
    if hits:
        print(path.name, hits)
PY
