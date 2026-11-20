"""Integrity checks for versioned packets; no task rules live here."""
import hashlib
import json
from pathlib import Path
from .session import BindingError

ROOT = Path(__file__).resolve().parents[2]
RELEASE = ROOT / 'data/expanded'


def inputs(case, variant):
    if case not in {p.name for p in RELEASE.iterdir() if p.is_dir()}:
        raise BindingError('Unknown English case')
    packet = RELEASE / case
    manifest = json.loads((packet / 'MANIFEST.json').read_text())
    if variant not in manifest:
        raise BindingError('Unknown English variant')
    folder = packet / 'variants' / variant
    paths = {str(p.relative_to(folder)): p for p in folder.rglob('*') if p.is_file()}
    if set(paths) != set(manifest[variant]) or any(p.is_symlink() for p in folder.rglob('*')):
        raise BindingError('English packet file set changed')
    if any(hashlib.sha256(paths[k].read_bytes()).hexdigest() != v for k, v in manifest[variant].items()):
        raise BindingError('English packet contents changed')
    return folder / 'inputs'
