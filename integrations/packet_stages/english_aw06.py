"""Versioned English presentation of AW06; private truth remains host-side."""
import hashlib
from pathlib import Path
from .authored import SOURCE, read_json
from .session import BindingError

ROOT = SOURCE.parent.parent
PACKET = ROOT / 'data/expanded/AW06'


def inputs(variant='full'):
    manifest = read_json(PACKET / 'MANIFEST.json')
    if variant not in manifest:
        raise BindingError('Unknown English AW06 variant')
    folder = PACKET / 'variants' / variant
    paths = {str(p.relative_to(folder)): p for p in folder.rglob('*') if p.is_file()}
    if set(paths) != set(manifest[variant]) or any(p.is_symlink() for p in folder.rglob('*')):
        raise BindingError('English packet file set changed')
    for name, expected in manifest[variant].items():
        if hashlib.sha256(paths[name].read_bytes()).hexdigest() != expected:
            raise BindingError('English packet contents changed')
    return folder / 'inputs'
