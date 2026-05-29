"""Telegram Function Calling tools."""

import random
from datetime import datetime

from .http_client import _get
from .registry import tool


@tool('get_random_image', 'Run the get_random_image utility.', {'properties': {'type': {'default': 'wallpaper',
                         'description': 'type parameter.',
                         'enum': ['wallpaper', 'avatar', 'anime'],
                         'type': 'string'}},
 'required': [],
 'type': 'object'})
async def _random_image(type: str='wallpaper') -> dict:
    urls = {'wallpaper': 'https://api.aa1.cn/api/api-bizhi/', 'avatar': 'https://api.aa1.cn/api/api-touxiang/', 'anime': 'https://api.aa1.cn/api/api-dongman/'}
    r = await _get(urls.get(type, urls['wallpaper']))
    return r

@tool('get_douyin_video', 'Run the get_douyin_video utility.', {'properties': {'url': {'description': 'URL.', 'type': 'string'}},
 'required': ['url'],
 'type': 'object'})
async def _video_parse(url: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-jiexi/', {'url': url})
    return r

@tool('get_music_search', 'Run the get_music_search utility.', {'properties': {'keyword': {'description': 'Optional search keyword.', 'type': 'string'}},
 'required': ['keyword'],
 'type': 'object'})
async def _music(keyword: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-music/', {'keyword': keyword})
    return r

@tool('get_movie_top', 'Run the get_movie_top utility.', {'properties': {'type': {'default': 'hot',
                         'description': 'type parameter.',
                         'enum': ['hot', 'top250', 'upcoming'],
                         'type': 'string'}},
 'required': [],
 'type': 'object'})
async def _movie(type: str='hot') -> dict:
    r = await _get('https://api.aa1.cn/api/api-movie/', {'type': type})
    return r

@tool('get_weibo_content', 'Run the get_weibo_content utility.', {'properties': {'keyword': {'description': 'Optional search keyword.', 'type': 'string'}},
 'required': ['keyword'],
 'type': 'object'})
async def _weibo(keyword: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-weibo/', {'keyword': keyword})
    return r

@tool('text_to_pinyin', 'Run the text_to_pinyin utility.', {'properties': {'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['text'],
 'type': 'object'})
async def _pinyin(text: str) -> dict:
    r = await _get('https://api.aa1.cn/api/api-pinyin/', {'text': text})
    return r

@tool('word_count', 'Run the word_count utility.', {'properties': {'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['text'],
 'type': 'object'})
async def _word_count(text: str) -> dict:
    chars = len(text)
    words = len(text.split())
    sentences = text.count('unavailable') + text.count('.') + text.count('unavailable') + text.count('unavailable')
    return {'characters': chars, 'words': words, 'sentences': max(sentences, 1)}

@tool('morse_code', 'Run the morse_code utility.', {'properties': {'action': {'default': 'encode',
                           'description': 'action parameter.',
                           'enum': ['encode', 'decode'],
                           'type': 'string'},
                'text': {'description': 'Input text.', 'type': 'string'}},
 'required': ['text'],
 'type': 'object'})
async def _morse(text: str, action: str='encode') -> dict:
    MORSE = {'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.', 'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..', 'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.', 'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-', 'Y': '-.--', 'Z': '--..', '0': '-----', '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....', '6': '-....', '7': '--...', '8': '---..', '9': '----.', ' ': '/'}
    if action == 'encode':
        result = ' '.join((MORSE.get(c.upper(), c) for c in text))
    else:
        REV = {v: k for k, v in MORSE.items()}
        result = ''.join((REV.get(c, c) for c in text.split(' ')))
    return {'input': text, 'output': result, 'action': action}

@tool('get_current_time', 'Run the get_current_time utility.', {'properties': {'timezone': {'default': 'Asia/Shanghai',
                             'description': 'timezone parameter.',
                             'type': 'string'}},
 'required': [],
 'type': 'object'})
async def _current_time(timezone: str='Asia/Shanghai') -> dict:
    import zoneinfo
    tz = zoneinfo.ZoneInfo(timezone)
    now = datetime.now(tz)
    return {'time': now.strftime('%Y-%m-%d %H:%M:%S'), 'timezone': timezone, 'weekday': now.strftime('%A')}

@tool('random_number', 'Run the random_number utility.', {'properties': {'max': {'default': 100, 'description': 'max parameter.', 'type': 'integer'},
                'min': {'default': 1, 'description': 'min parameter.', 'type': 'integer'}},
 'required': [],
 'type': 'object'})
async def _random_number(min: int=1, max: int=100) -> dict:
    return {'result': random.randint(min, max), 'range': f'{min}-{max}'}
