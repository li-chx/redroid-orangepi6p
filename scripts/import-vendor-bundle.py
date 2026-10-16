#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Import the pinned vendor tar.gz with an explicit file whitelist and hashes."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile

from common import ROOT, WORK, LOCK, checked

BUNDLE = json.loads((ROOT / 'config/vendor-bundle.lock.json').read_text())


def verify_vendor(directory):
    for item in LOCK['vendor_files']:
        path = (directory / item['source'].removeprefix('vendor/')).resolve()
        if not path.is_relative_to(directory.resolve()):
            raise RuntimeError('Vendor input escapes its directory')
        checked(path, item['sha256'])


def import_bundle(archive):
    checked(archive, BUNDLE['sha256'])
    destination = WORK / 'vendor-input'
    if destination.exists():
        verify_vendor(destination)
        return destination
    metadata = {'inputs.lock.json', 'PROVENANCE.json', 'README.md', 'NOTICE', 'SHA256SUMS'}
    allowed = metadata | {item['source'] for item in LOCK['vendor_files']}
    directories = {'.'} | {str(parent) for path in allowed for parent in PurePosixPath(path).parents}
    with tempfile.TemporaryDirectory(dir=WORK / 'tmp', prefix='vendor-import-') as temporary:
        stage = Path(temporary)
        seen = set()
        size = 0
        with tarfile.open(archive, 'r:gz') as bundle:
            for member in bundle:
                path = PurePosixPath(member.name)
                if path.is_absolute() or '..' in path.parts or not path.parts or path.parts[0] != BUNDLE['root_directory']:
                    raise RuntimeError('Unexpected vendor bundle path')
                relative = str(path.relative_to(BUNDLE['root_directory']))
                if member.isdir() and relative in directories:
                    continue
                if not member.isfile() or relative not in allowed or relative in seen:
                    raise RuntimeError('Unexpected or duplicate vendor bundle file')
                size += member.size
                if size > 128 * 1024**2:
                    raise RuntimeError('Vendor bundle contents exceed the size limit')
                target = stage / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with bundle.extractfile(member) as source, target.open('xb') as output:
                    shutil.copyfileobj(source, output)
                target.chmod(0o755 if relative.startswith('vendor/bin/') else 0o644)
                seen.add(relative)
        if seen != allowed:
            raise RuntimeError('Vendor bundle is missing required files')
        hashes = {}
        for row in (stage / 'SHA256SUMS').read_text().splitlines():
            match = re.fullmatch(r'([0-9a-f]{64})  (.+)', row)
            if not match or match[2] not in allowed - {'SHA256SUMS'} or match[2] in hashes:
                raise RuntimeError('Unexpected vendor bundle checksum entry')
            hashes[match[2]] = match[1]
        if set(hashes) != allowed - {'SHA256SUMS'}:
            raise RuntimeError('Incomplete vendor bundle checksum manifest')
        for name, expected in hashes.items():
            checked(stage / name, expected)
        if json.loads((stage / 'inputs.lock.json').read_text()) != LOCK:
            raise RuntimeError('Vendor bundle catalog differs from this project')
        verify_vendor(stage / 'vendor')
        (stage / 'vendor').rename(destination)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, nargs='?', default=WORK / 'downloads' / BUNDLE['filename'])
    args = parser.parse_args()
    destination = import_bundle(args.archive)
    print('Verified vendor inputs:', destination)


if __name__ == '__main__':
    main()
