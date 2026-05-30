"""Telegram Function Calling tools."""

from datetime import datetime

from .http_client import _get
from .registry import tool
from .safe_math import evaluate_math_expression


@tool('get_crypto_price', 'Run the get_crypto_price utility.', {'properties': {'coin': {'description': 'Coin identifier.', 'type': 'string'}},
 'required': ['coin'],
 'type': 'object'})
async def _crypto(coin: str) -> dict:
    try:
        r = await _get(f'https://api.coinbase.com/v2/prices/{coin}-USD/spot', timeout=8)
        if isinstance(r, dict) and 'data' in r:
            return {'coin': coin, 'price_usd': r['data'].get('amount'), 'currency': 'USD'}
    except Exception as exc:
        _log.debug("lima_fc_tools/finance_math_tools.py: {}", type(exc).__name__)
    return {'coin': coin, 'error': 'Price unavailable (blocked in China)'}

@tool('get_stock_price', 'Run the get_stock_price utility.', {'properties': {'code': {'description': 'Stock code.', 'type': 'string'}},
 'required': ['code'],
 'type': 'object'})
async def _stock(code: str) -> dict:
    try:
        r = await _get(f'https://hq.sinajs.cn/list={code}', timeout=6)
        if isinstance(r, str) and ',' in r:
            parts = r.split(',')
            name = parts[0].split('=')[-1].strip('"')
            return {'code': code, 'name': name, 'open': parts[1], 'close_yesterday': parts[2], 'current': parts[3], 'high': parts[4], 'low': parts[5]}
    except Exception as exc:
        _log.debug("lima_fc_tools/finance_math_tools.py: {}", type(exc).__name__)
    return {'code': code, 'error': 'unavailable'}

@tool('calculate', 'Evaluate a safe math expression.', {'properties': {'expression': {'description': 'Math expression.', 'type': 'string'}},
 'required': ['expression'],
 'type': 'object'})
async def _calculate(expression: str) -> dict:
    try:
        result = evaluate_math_expression(expression)
        return {'expression': expression, 'result': result}
    except Exception as e:
        return {'error': str(e)}

@tool('convert_timezone', 'Run the convert_timezone utility.', {'properties': {'from_tz': {'description': 'Source timezone.', 'type': 'string'},
                'time': {'description': 'Time string.', 'type': 'string'},
                'to_tz': {'description': 'Target timezone.', 'type': 'string'}},
 'required': ['time', 'from_tz', 'to_tz'],
 'type': 'object'})
async def _timezone(time: str, from_tz: str, to_tz: str) -> dict:
    import zoneinfo
    try:
        if len(time) <= 5:
            time = f'2026-01-01 {time}'
        dt = datetime.fromisoformat(time)
        src = zoneinfo.ZoneInfo(from_tz)
        dst = zoneinfo.ZoneInfo(to_tz)
        dt_src = dt.replace(tzinfo=src)
        dt_dst = dt_src.astimezone(dst)
        return {'from': f"{dt_src.strftime('%H:%M')} ({from_tz})", 'to': f"{dt_dst.strftime('%H:%M')} ({to_tz})"}
    except Exception as e:
        return {'error': str(e)}

@tool('convert_units', 'Run the convert_units utility.', {'properties': {'from_unit': {'description': 'Source unit.', 'type': 'string'},
                'to_unit': {'description': 'Target unit.', 'type': 'string'},
                'value': {'description': 'Numeric value.', 'type': 'number'}},
 'required': ['value', 'from_unit', 'to_unit'],
 'type': 'object'})
async def _convert_units(value: float, from_unit: str, to_unit: str) -> dict:
    conversions = {('km', 'mile'): 0.621371, ('mile', 'km'): 1.60934, ('kg', 'lb'): 2.20462, ('lb', 'kg'): 0.453592, ('m', 'ft'): 3.28084, ('ft', 'm'): 0.3048, ('cm', 'inch'): 0.393701, ('inch', 'cm'): 2.54, ('celsius', 'fahrenheit'): lambda v: v * 9 / 5 + 32, ('fahrenheit', 'celsius'): lambda v: (v - 32) * 5 / 9, ('m2', 'ft2'): 10.7639, ('ft2', 'm2'): 0.092903, ('l', 'gallon'): 0.264172, ('gallon', 'l'): 3.78541}
    key = (from_unit.lower(), to_unit.lower())
    factor = conversions.get(key)
    if factor is None:
        return {'error': f'Unsupported: {from_unit}unavailable{to_unit}'}
    result = factor(value) if callable(factor) else value * factor
    return {'value': value, 'from': from_unit, 'to': to_unit, 'result': round(result, 4)}
