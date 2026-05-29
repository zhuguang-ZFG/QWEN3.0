"""Telegram Function Calling tools."""


from .http_client import _get
from .registry import tool


@tool('lookup_word', 'Look up dictionary information for a word.', {'properties': {'word': {'description': 'Word to look up.', 'type': 'string'}},
 'required': ['word'],
 'type': 'object'})
async def _dictionary(word: str) -> dict:
    r = await _get(f'https://api.dictionaryapi.dev/api/v2/entries/en/{word}')
    if isinstance(r, list) and r:
        e = r[0]
        meanings = [{'pos': m.get('partOfSpeech'), 'def': m['definitions'][0]['definition']} for m in e.get('meanings', [])[:3] if m.get('definitions')]
        return {'word': word, 'phonetic': e.get('phonetic', ''), 'meanings': meanings}
    return {'error': f"Word '{word}' not found"}

@tool('get_country_info', 'Run the get_country_info utility.', {'properties': {'name': {'description': 'Name.', 'type': 'string'}},
 'required': ['name'],
 'type': 'object'})
async def _country(name: str) -> dict:
    r = await _get(f'https://restcountries.com/v3.1/name/{name}')
    if isinstance(r, list) and r:
        c = r[0]
        return {'name': c.get('name', {}).get('common'), 'capital': c.get('capital', [None])[0], 'population': c.get('population'), 'region': c.get('region'), 'languages': list(c.get('languages', {}).values())[:3]}
    return {'error': f"Country '{name}' not found"}

@tool('get_github_user', 'Look up a GitHub user profile.', {'properties': {'username': {'description': 'User name.', 'type': 'string'}},
 'required': ['username'],
 'type': 'object'})
async def _github_user(username: str) -> dict:
    r = await _get(f'https://api.github.com/users/{username}')
    if isinstance(r, dict) and r.get('login'):
        return {'login': r['login'], 'name': r.get('name'), 'bio': r.get('bio'), 'repos': r.get('public_repos'), 'followers': r.get('followers')}
    return {'error': f"User '{username}' not found"}

@tool('get_npm_package', 'Run the get_npm_package utility.', {'properties': {'package': {'description': 'Package name.', 'type': 'string'}},
 'required': ['package'],
 'type': 'object'})
async def _npm(package: str) -> dict:
    r = await _get(f'https://registry.npmjs.org/{package}/latest')
    if isinstance(r, dict) and r.get('name'):
        return {'name': r['name'], 'version': r.get('version'), 'description': r.get('description', '')[:80]}
    return {'error': f"'{package}' not found"}

@tool('get_pypi_package', 'Run the get_pypi_package utility.', {'properties': {'package': {'description': 'Package name.', 'type': 'string'}},
 'required': ['package'],
 'type': 'object'})
async def _pypi(package: str) -> dict:
    r = await _get(f'https://pypi.org/pypi/{package}/json')
    if isinstance(r, dict) and r.get('info'):
        i = r['info']
        return {'name': i.get('name'), 'version': i.get('version'), 'summary': i.get('summary', '')[:80]}
    return {'error': f"'{package}' not found"}

@tool('get_trivia', 'Run the get_trivia utility.', {'properties': {'category': {'default': 9, 'description': 'News category.', 'type': 'integer'}},
 'required': [],
 'type': 'object'})
async def _trivia(category: int=9) -> dict:
    r = await _get('https://opentdb.com/api.php', {'amount': 1, 'category': category, 'type': 'multiple'})
    if isinstance(r, dict) and r.get('results'):
        q = r['results'][0]
        return {'question': q.get('question'), 'correct_answer': q.get('correct_answer'), 'category': q.get('category')}
    return {'error': 'No trivia available'}

@tool('get_advice', 'Run the get_advice utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _advice() -> dict:
    r = await _get('https://api.adviceslip.com/advice')
    if isinstance(r, str):
        import json as _j
        r = _j.loads(r)
    return {'advice': r.get('slip', {}).get('advice', '')} if isinstance(r, dict) else {'error': 'unavailable'}

@tool('get_random_fact', 'Run the get_random_fact utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _fact() -> dict:
    r = await _get('https://uselessfacts.jsph.pl/api/v2/facts/random', {'language': 'en'})
    return {'fact': r.get('text')} if isinstance(r, dict) else {'error': 'unavailable'}

@tool('get_iss_location', 'Run the get_iss_location utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _iss() -> dict:
    r = await _get('http://api.open-notify.org/iss-now.json')
    if isinstance(r, dict) and r.get('iss_position'):
        return r['iss_position']
    return {'error': 'unavailable'}

@tool('get_people_in_space', 'Run the get_people_in_space utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _astros() -> dict:
    r = await _get('http://api.open-notify.org/astros.json')
    return {'number': r.get('number'), 'people': r.get('people')} if isinstance(r, dict) else {'error': 'unavailable'}

@tool('predict_name_info', 'Run the predict_name_info utility.', {'properties': {'name': {'description': 'Name.', 'type': 'string'}},
 'required': ['name'],
 'type': 'object'})
async def _name_predict(name: str) -> dict:
    age = await _get('https://api.agify.io', {'name': name})
    gender = await _get('https://api.genderize.io', {'name': name})
    nation = await _get('https://api.nationalize.io', {'name': name})
    return {'name': name, 'predicted_age': age.get('age') if isinstance(age, dict) else None, 'predicted_gender': gender.get('gender') if isinstance(gender, dict) else None, 'top_country': nation.get('country', [{}])[0].get('country_id') if isinstance(nation, dict) else None}

@tool('get_ip_details', 'Run the get_ip_details utility.', {'properties': {'ip': {'description': 'Public IP address.', 'type': 'string'}},
 'required': ['ip'],
 'type': 'object'})
async def _ipinfo(ip: str) -> dict:
    r = await _get(f'https://ipinfo.io/{ip}/json')
    return r if isinstance(r, dict) else {'error': 'unavailable'}
