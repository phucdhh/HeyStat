
import os.path
import json
from functools import lru_cache

from .utils import conf

i18n_msgs = None
_code = None

def get_language():
    global _code
    return _code

def set_language(code):
    global _code
    global i18n_msgs
    if _code != code:
        _code = code
        i18n_msgs = None

def _i18n_path():
    i18n_path = conf.get('i18n_path', None)
    if i18n_path is None:
        i18n_path = os.path.join(conf.get('home'), 'i18n', 'json')
    return i18n_path


@lru_cache(None)
def catalogue_for(code):
    """The shipped translation file covering ``code``, or None.

    ``fr-FR`` is served by ``fr.json``, so the tag a browser sends is not the tag
    to ask the server for.
    """
    if not code:
        return None
    path = _i18n_path()
    code = code.lower()
    for candidate in (code, code.split('-')[0]):
        if os.path.exists(os.path.join(path, candidate + '.json')):
            return candidate
    return None


def _parse_accept_language(header):
    """The codes of an Accept-Language header, best preference first."""
    codes = []
    for part in (header or '').split(','):
        tag, _, params = part.strip().partition(';')
        try:
            quality = float(params.partition('q=')[2]) if 'q=' in params else 1.0
        except ValueError:
            quality = 0.0
        tag = tag.strip().lower()
        if tag and tag != '*' and quality > 0:
            codes.append((quality, len(codes), tag))
    return [tag for _, _, tag in sorted(codes, key=lambda c: (-c[0], c[1]))]


def best_language(header):
    """The language to serve for an ``Accept-Language`` header.

    Only a code with a shipped catalogue is chosen, and English stands for the
    source strings, so it always qualifies.  Reporting anything else as the
    session's language makes the browser fetch ``/i18n/<code>.json``, which has no
    file behind it, and it logs a failed request on every page load.
    """
    for code in _parse_accept_language(header):
        if code.split('-')[0] == 'en':
            return 'en'
        found = catalogue_for(code)
        if found:
            return found
    return 'en'


@lru_cache(None)
def _load_translations(code):
    if code:
        i18n_root = os.path.join(_i18n_path(), code + '.json')
        if os.path.exists(i18n_root):
            with open(i18n_root, 'r', encoding='utf-8') as stream:
                i18n_def = json.load(stream)
                return i18n_def['locale_data']['messages']

    return {}

def _(value):
    global _code
    global i18n_msgs
    if i18n_msgs is None:
        i18n_msgs = _load_translations(_code)

    translation = value

    if i18n_msgs:
        trans = i18n_msgs.get(value)
        if trans is not None:
            translation = trans[0].strip()
            if translation == '':
                translation = value

    return translation
