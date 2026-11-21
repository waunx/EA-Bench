"""Validated release registry. Solver visibility is restricted to one public packet."""
import hashlib
import json
from pathlib import Path
from .paths import ROOT, DATA


def entries():
    return json.loads((ROOT / 'benchmark/manifest.json').read_text())['episodes']


def get_entry(episode_id):
    matches = [e for e in entries()
               if episode_id in (e['id'], f"{e['cohort']}:{e['case']}:{e['variant']}")]
    if len(matches) != 1:
        raise ValueError(f'Unknown episode: {episode_id}')
    return matches[0]


def verify_entry(entry):
    folder = DATA / entry['packet']
    for name, expected in entry['files'].items():
        path = folder / name
        if not path.is_file() or path.is_symlink():
            raise ValueError(f'Missing or invalid input: {entry["id"]}/{name}')
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f'Input hash mismatch: {entry["id"]}/{name}')
    return folder
