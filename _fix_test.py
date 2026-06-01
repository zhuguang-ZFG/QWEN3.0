import sys
p = sys.argv[1]
t = open(p, encoding='utf-8').read()
t = t.replace('"LiMa Admin Console" in html', '"&#x674e;&#x9a6c;" in html')
t = t.replace('"????" not in html', '"��" not in html')
open(p, 'w', encoding='utf-8').write(t)
print('done')
