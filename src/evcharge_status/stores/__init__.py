import importlib
from urllib.parse import parse_qs, urlparse


def get_store(uri: str):
    parts = urlparse(uri)
    scheme = parts.scheme
    if not scheme:
        scheme = 'file'
    
    if '.' in scheme:
        # no, don't do that.
        raise ValueError('Store scheme may not contain "."')

    module_name = f'.{scheme}'
    module = importlib.import_module(module_name, __package__)
    return module.Store(parts.path, **{k: v[-1] for k, v in parse_qs(parts.query)})