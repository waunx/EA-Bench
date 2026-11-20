"""Fetch the public evaluation bundle and verify it before extraction."""
import hashlib
import json
from pathlib import Path
import tarfile
import tempfile
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def main():
    release = json.loads((ROOT / 'benchmark/data-release.json').read_text())
    if (ROOT / 'data').exists():
        raise FileExistsError('data/ already exists; move it aside before installing a new bundle')
    with tempfile.TemporaryDirectory(prefix='ea-bench-download-') as folder:
        archive = Path(folder) / 'data.tar.gz'
        urllib.request.urlretrieve(release['url'], archive)
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        if digest != release['sha256']:
            raise ValueError('Data checksum mismatch')
        with tarfile.open(archive) as bundle:
            members = bundle.getmembers()
            for member in members:
                path = Path(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != 'data':
                    raise ValueError('Invalid path in evaluation bundle')
                if not member.isfile() and not member.isdir():
                    raise ValueError('Links and special files are not allowed')
            for member in members:
                target = ROOT / member.name
                if member.isdir():target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with bundle.extractfile(member) as source, target.open('wb') as output:
                        import shutil
                        shutil.copyfileobj(source, output)
    print('Verified evaluation data installed in data/.')

if __name__ == '__main__':main()
