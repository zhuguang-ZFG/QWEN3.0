import sys, os
sys.path.insert(0, '/opt/lima-router')

from context_pipeline import RequestContext
from context_pipeline.factory import build_default_pipeline

pipe = build_default_pipeline()

# Test 1: Cursor IDE coding
ctx = pipe.process(RequestContext(
    headers={'user-agent': 'cursor/1.0'},
    messages=[{'role': 'user', 'content': 'fix the bug'}],
    path='/v1/chat/completions',
))
assert ctx.ide == 'cursor'
assert ctx.scenario == 'coding'
assert len(ctx.processors_applied) == 5
print('Test 1 OK: ide=cursor, scenario=coding, prompt=%d chars' % len(ctx.system_prompt))

# Test 2: Kiro IDE
ctx = pipe.process(RequestContext(
    headers={'user-agent': 'kiro/2.0'},
    messages=[{'role': 'user', 'content': 'add endpoint'}],
))
assert ctx.ide == 'kiro'
assert ctx.scenario == 'coding'
print('Test 2 OK: ide=kiro')

# Test 3: Chat
ctx = pipe.process(RequestContext(
    headers={'user-agent': 'python/3.10'},
    messages=[{'role': 'user', 'content': 'what is FastAPI?'}],
))
assert ctx.ide == ''
assert ctx.scenario == 'chat'
print('Test 3 OK: scenario=chat')

# Test 4: Vision
ctx = pipe.process(RequestContext(
    headers={'user-agent': 'cursor/1.0'},
    messages=[{'role': 'user', 'content': [{'type': 'image_url', 'image_url': {'url': 'x'}}]}],
))
assert ctx.scenario == 'vision'
print('Test 4 OK: scenario=vision')

# Test 5: Pipeline stages
assert pipe.stages == ['ide_detection', 'scenario_classification', 'code_context', 'prompt_composition', 'cache_optimization']
print('Test 5 OK: 5 stages')

print('')
print('ALL 5 E2E TESTS PASSED')
