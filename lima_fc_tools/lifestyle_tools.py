"""Telegram Function Calling tools."""


from .http_client import _get
from .registry import tool


@tool('get_recipe', 'Run the get_recipe utility.', {'properties': {'dish': {'description': 'Dish name.', 'type': 'string'}},
 'required': ['dish'],
 'type': 'object'})
async def _recipe(dish: str) -> dict:
    r = await _get('https://www.themealdb.com/api/json/v1/1/search.php', {'s': dish}, timeout=8)
    if isinstance(r, dict) and r.get('meals'):
        m = r['meals'][0]
        ingredients = [m.get(f'strIngredient{i}') for i in range(1, 10) if m.get(f'strIngredient{i}')]
        return {'name': m.get('strMeal'), 'category': m.get('strCategory'), 'area': m.get('strArea'), 'instructions': (m.get('strInstructions') or '')[:400], 'ingredients': ingredients}
    return {'dish': dish, 'note': 'unavailable'}

@tool('get_lunar_date', 'Run the get_lunar_date utility.', {'properties': {'date': {'default': '',
                         'description': 'Date in YYYY-MM-DD format.',
                         'type': 'string'}},
 'required': [],
 'type': 'object'})
async def _lunar(date: str='') -> dict:
    params = {'date': date} if date else {}
    r = await _get('https://api.aa1.cn/api/api-nongli/', params)
    return r

@tool('get_constellation', 'Run the get_constellation utility.', {'properties': {'name': {'description': 'Name.', 'type': 'string'}},
 'required': ['name'],
 'type': 'object'})
async def _constellation(name: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-xingzuo/', {'name': name})
    return r

@tool('get_joke', 'Run the get_joke utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _joke() -> dict:
    r = await _get('https://api.aa1.cn/api/api-xiaohua/')
    return r

@tool('get_poetry', 'Run the get_poetry utility.', {'properties': {'keyword': {'default': '',
                            'description': 'Optional search keyword.',
                            'type': 'string'}},
 'required': [],
 'type': 'object'})
async def _poetry(keyword: str='') -> dict:
    params = {'keyword': keyword} if keyword else {}
    r = await _get('https://api.aa1.cn/api/api-shici/', params)
    return r

@tool('get_train_info', 'Run the get_train_info utility.', {'properties': {'date': {'description': 'Date in YYYY-MM-DD format.', 'type': 'string'},
                'from_city': {'description': 'from_city parameter.', 'type': 'string'},
                'to_city': {'description': 'to_city parameter.', 'type': 'string'}},
 'required': ['from_city', 'to_city', 'date'],
 'type': 'object'})
async def _train(from_city: str, to_city: str, date: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-train/', {'from': from_city, 'to': to_city, 'date': date})
    return r

@tool('get_random_quote', 'Run the get_random_quote utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _quote() -> dict:
    r = await _get('https://api.aa1.cn/api/api-mingyan/')
    return r

@tool('get_bmi', 'Calculate BMI.', {'properties': {'height': {'description': 'Height in centimeters.', 'type': 'number'},
                'weight': {'description': 'Weight in kilograms.', 'type': 'number'}},
 'required': ['height', 'weight'],
 'type': 'object'})
async def _bmi(height: float, weight: float) -> dict:
    h = height / 100
    bmi = round(weight / (h * h), 1)
    if bmi < 18.5:
        level = 'unavailable'
    elif bmi < 24:
        level = 'unavailable'
    elif bmi < 28:
        level = 'unavailable'
    else:
        level = 'unavailable'
    return {'bmi': bmi, 'level': level, 'height_cm': height, 'weight_kg': weight}
