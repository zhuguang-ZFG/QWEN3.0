"""Telegram Function Calling tools."""


from .http_client import _get
from .registry import tool


@tool('get_weather_forecast', 'Run the get_weather_forecast utility.', {'properties': {'latitude': {'description': 'latitude parameter.', 'type': 'number'},
                'longitude': {'description': 'longitude parameter.', 'type': 'number'}},
 'required': ['latitude', 'longitude'],
 'type': 'object'})
async def _weather_forecast(latitude: float, longitude: float) -> dict:
    r = await _get('https://api.open-meteo.com/v1/forecast', {'latitude': latitude, 'longitude': longitude, 'current_weather': 'true', 'daily': 'temperature_2m_max,temperature_2m_min,precipitation_sum,weathercode', 'timezone': 'Asia/Shanghai'})
    return r

@tool('search_music', 'Run the search_music utility.', {'properties': {'keyword': {'description': 'Optional search keyword.', 'type': 'string'},
                'limit': {'default': 5, 'description': 'limit parameter.', 'type': 'integer'}},
 'required': ['keyword'],
 'type': 'object'})
async def _search_music(keyword: str, limit: int=5) -> dict:
    r = await _get('https://itunes.apple.com/search', {'term': keyword, 'limit': limit, 'media': 'music'})
    results = r.get('results', []) if isinstance(r, dict) else []
    return {'results': [{'track': t.get('trackName'), 'artist': t.get('artistName'), 'album': t.get('collectionName')} for t in results[:limit]]}

@tool('search_cocktail', 'Run the search_cocktail utility.', {'properties': {'name': {'description': 'Name.', 'type': 'string'}},
 'required': ['name'],
 'type': 'object'})
async def _cocktail(name: str) -> dict:
    r = await _get('https://www.thecocktaildb.com/api/json/v1/1/search.php', {'s': name})
    drinks = r.get('drinks', []) if isinstance(r, dict) else []
    if not drinks:
        return {'error': 'No cocktail found'}
    d = drinks[0]
    ingredients = [d.get(f'strIngredient{i}') for i in range(1, 8) if d.get(f'strIngredient{i}')]
    return {'name': d.get('strDrink'), 'category': d.get('strCategory'), 'instructions': d.get('strInstructions', '')[:300], 'ingredients': ingredients}

@tool('get_random_poetry', 'Run the get_random_poetry utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _random_poetry() -> dict:
    r = await _get('https://poetrydb.org/random/1')
    if isinstance(r, list) and r:
        p = r[0]
        return {'title': p.get('title'), 'author': p.get('author'), 'lines': p.get('lines', [])[:10]}
    return {'error': 'No poetry found'}

@tool('get_earthquake', 'Run the get_earthquake utility.', {'properties': {'limit': {'default': 5, 'description': 'limit parameter.', 'type': 'integer'},
                'min_magnitude': {'default': 4.0,
                                  'description': 'min_magnitude parameter.',
                                  'type': 'number'}},
 'required': [],
 'type': 'object'})
async def _earthquake(min_magnitude: float=4.0, limit: int=5) -> dict:
    r = await _get('https://earthquake.usgs.gov/fdsnws/event/1/query', {'format': 'geojson', 'limit': limit, 'orderby': 'time', 'minmagnitude': min_magnitude})
    features = r.get('features', []) if isinstance(r, dict) else []
    return {'earthquakes': [{'place': f['properties'].get('place'), 'magnitude': f['properties'].get('mag'), 'time': f['properties'].get('time')} for f in features[:limit]]}

@tool('get_nasa_apod', 'Run the get_nasa_apod utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _nasa_apod() -> dict:
    r = await _get('https://api.nasa.gov/planetary/apod', {'api_key': 'DEMO_KEY'})
    if isinstance(r, dict):
        return {'title': r.get('title'), 'explanation': r.get('explanation', '')[:300], 'url': r.get('url'), 'date': r.get('date')}
    return {'error': 'NASA API unavailable'}

@tool('get_spacex_launch', 'Run the get_spacex_launch utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _spacex() -> dict:
    r = await _get('https://api.spacexdata.com/v5/launches/latest')
    if isinstance(r, dict):
        return {'name': r.get('name'), 'date': r.get('date_local'), 'success': r.get('success'), 'details': (r.get('details') or '')[:200], 'rocket': r.get('rocket')}
    return {'error': 'SpaceX API unavailable'}

@tool('search_tv_show', 'Run the search_tv_show utility.', {'properties': {'query': {'description': 'Search query.', 'type': 'string'}},
 'required': ['query'],
 'type': 'object'})
async def _tv_show(query: str) -> dict:
    r = await _get('http://api.tvmaze.com/search/shows', {'q': query})
    if isinstance(r, list):
        return {'results': [{'name': s['show'].get('name'), 'genres': s['show'].get('genres', []), 'rating': s['show'].get('rating', {}).get('average'), 'summary': (s['show'].get('summary') or '')[:100]} for s in r[:5]]}
    return {'error': 'No results'}

@tool('get_cat_fact', 'Run the get_cat_fact utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _cat_fact() -> dict:
    r = await _get('https://catfact.ninja/fact')
    return r if isinstance(r, dict) else {'fact': str(r)}

@tool('get_random_activity', 'Run the get_random_activity utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _bored() -> dict:
    r = await _get('https://bored-api.appbrewery.com/random')
    if isinstance(r, dict):
        return {'activity': r.get('activity'), 'type': r.get('type'), 'participants': r.get('participants')}
    return {'error': 'API unavailable'}

@tool('get_random_dog', 'Run the get_random_dog utility.', {'properties': {}, 'required': [], 'type': 'object'})
async def _dog() -> dict:
    r = await _get('https://dog.ceo/api/breeds/image/random')
    return r if isinstance(r, dict) else {'error': 'unavailable'}

@tool('get_astronomy', 'Run the get_astronomy utility.', {'properties': {'latitude': {'description': 'latitude parameter.', 'type': 'number'},
                'longitude': {'description': 'longitude parameter.', 'type': 'number'}},
 'required': ['latitude', 'longitude'],
 'type': 'object'})
async def _astronomy(latitude: float, longitude: float) -> dict:
    r = await _get('http://www.7timer.info/bin/api.pl', {'lon': longitude, 'lat': latitude, 'product': 'astro', 'output': 'json'})
    return r if isinstance(r, dict) else {'error': 'unavailable'}

@tool('get_sunrise_sunset', 'Run the get_sunrise_sunset utility.', {'properties': {'latitude': {'description': 'latitude parameter.', 'type': 'number'},
                'longitude': {'description': 'longitude parameter.', 'type': 'number'}},
 'required': ['latitude', 'longitude'],
 'type': 'object'})
async def _sunrise(latitude: float, longitude: float) -> dict:
    r = await _get('https://api.open-meteo.com/v1/forecast', {'latitude': latitude, 'longitude': longitude, 'daily': 'sunrise,sunset', 'timezone': 'Asia/Shanghai', 'forecast_days': 1})
    if isinstance(r, dict) and 'daily' in r:
        d = r['daily']
        return {'sunrise': d.get('sunrise', [''])[0], 'sunset': d.get('sunset', [''])[0]}
    return {'error': 'unavailable'}
