import subprocess, json, os, sys

env = os.environ.copy()
env['LIMA_API_KEY'] = 'xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw'
env['LIMA_CODE_SERVER_URL'] = 'https://chat.donglicao.com'
env['LIMA_CODE_API_KEY'] = 'xHzP3Uk9EAJfzIoAjjvzxKebXnBIirm6ByYz_zo1vJw'

tests = [
    ('1+1等于几', 'simple'),
    ('什么是asyncio', 'chat'),
    ('写一个Python阶乘函数', 'coding_cn'),
    ('write a Python sort function', 'coding_en'),
    ('explain the GIL in Python', 'chat_en'),
]
results = []
for prompt, cat in tests:
    print(f'[{cat}] {prompt}...', end=' ', flush=True)
    try:
        r = subprocess.run(
            ['node', 'D:/GIT/deepcode-cli/node_modules/tsx/dist/cli.mjs',
             'D:/GIT/deepcode-cli/src/cli.tsx',
             '--headless', '-p', prompt, '--json'],
            capture_output=True, text=True, timeout=50, encoding='utf-8',
            cwd='D:/GIT/deepcode-cli', env=env)
        if r.returncode == 0:
            d = json.loads(r.stdout.strip())
            c = d.get('content', '')
            has_code = 'def ' in c or '```' in c
            print(f'OK len={len(c)} code={has_code}')
            results.append({'ok': True, 'cat': cat, 'len': len(c), 'has_code': has_code})
        else:
            print(f'FAIL rc={r.returncode} stderr={r.stderr[:60]}')
            results.append({'ok': False, 'cat': cat, 'error': r.stderr[:100]})
    except subprocess.TimeoutExpired:
        print('TIMEOUT')
        results.append({'ok': False, 'cat': cat, 'error': 'timeout'})

print()
ok = sum(1 for r in results if r.get('ok'))
print(f'Results: {ok}/{len(results)} passed')
for r in results:
    if r.get('ok'):
        print('  PASS [%s] len=%s code=%s' % (r.get('cat','?'), r.get('len',0), r.get('has_code')))
    else:
        print('  FAIL [%s] %s' % (r.get('cat','?'), r.get('error','')[:60]))
