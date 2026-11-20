"""Three explicit model roles; secrets are read from environment variables."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

_CONFIG = None


def load_config(path):
    global _CONFIG
    data = json.loads(Path(path).read_text())
    for role in ('solver', 'user', 'judge'):
        cfg = data[role]
        for key in ('model', 'base_url', 'api_key_env'):
            if not isinstance(cfg[key], str) or not cfg[key]:
                raise ValueError(f'{role}.{key} must be a nonempty string')
        if urlsplit(cfg['base_url']).scheme not in ('https', 'http'):
            raise ValueError(f'{role}.base_url must be an HTTP(S) URL')
        if cfg.get('wire_api', 'chat') not in ('chat', 'responses'):
            raise ValueError(f'{role}.wire_api must be chat or responses')
        if 'api_key' in cfg or 'auth_file' in cfg or 'credential_source' in cfg:
            raise ValueError('Use api_key_env; do not put secrets or private credential sources in configuration')
        cfg.setdefault('wire_api', 'chat')
        cfg.setdefault('max_tokens', 16384)
        cfg.setdefault('reasoning_effort', None)
        cfg.setdefault('timeout', 180)
    _CONFIG = data
    return data


def role_config(role):
    if _CONFIG is None:
        load_config(os.environ['EA_BENCH_CONFIG'])
    return _CONFIG[role]
