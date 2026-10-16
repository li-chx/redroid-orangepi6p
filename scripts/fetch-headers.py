#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch Android14 headers, pinning file contents independently of tar metadata."""
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
import urllib.request
from common import ROOT, WORK, checked

def header_files(path, item):
    files = {}
    size = 0
    with tarfile.open(path) as archive:
        for member in archive:
            # libcxx's out-of-tree ABI-header link is fetched separately below.
            if not (member.isfile() or member.isdir()):
                continue
            name = PurePosixPath(member.name)
            if name.is_absolute() or '..' in name.parts:
                raise RuntimeError('Unsafe header archive member')
            if member.isdir():
                continue
            if str(name) in files:
                raise RuntimeError('Duplicate header archive member')
            size += member.size
            if size > 64 * 1024**2:
                raise RuntimeError('Header archive contents exceed the size limit')
            files[str(name)] = archive.extractfile(member).read()
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in files.items()}
    tree = hashlib.sha256(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if tree != item['tree_sha256'] or len(files) != item['regular_files']:
        raise RuntimeError('Header file names or contents differ from the pinned tree: ' + item['file'])
    return files


def verify(path, item):
    if item['file'].endswith('.tar.gz'):
        return header_files(path, item)
    checked(path, item['sha256'])
    return None


def fetch(item):
    cache = WORK / 'cache' / item['file']
    cache.parent.mkdir(parents=True, exist_ok=True)
    if cache.exists():
        return cache, verify(cache, item)
    partial = cache.with_suffix(cache.suffix + '.partial')
    if partial.exists():
        raise RuntimeError('A partial header download already exists')
    try:
        with urllib.request.urlopen(item['url'], timeout=90) as response:
            data = response.read(8 * 1024**2 + 1)
        if len(data) > 8 * 1024**2:
            raise RuntimeError('Header download exceeds the size limit')
        if item['url'].endswith('format=TEXT'):
            data = base64.b64decode(data)
        with partial.open('xb') as stream:
            stream.write(data)
        files = verify(partial, item)
        partial.replace(cache)
        return cache, files
    finally:
        partial.unlink(missing_ok=True)


def main():
    headers = WORK / 'headers'
    headers.mkdir(parents=True, exist_ok=True)
    for item in json.loads((ROOT / 'config/header-sources.json').read_text()):
        cache, files = fetch(item)
        if files is not None:
            out = headers / item['file'][:-7]
            with tempfile.TemporaryDirectory(dir=WORK / 'tmp', prefix='headers-') as temporary:
                stage = Path(temporary) / 'include'
                stage.mkdir()
                for name, data in files.items():
                    destination = stage / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    destination.write_bytes(data)
                if out.exists():
                    shutil.rmtree(out)
                stage.rename(out)
        else:
            target = headers / 'libcxx' / item['file']
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(cache.read_bytes())
    print('Pinned Android14 headers ready under work/headers')


if __name__ == '__main__':
    main()
