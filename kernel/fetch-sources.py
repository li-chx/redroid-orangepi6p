#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify prepared source submodules and fetch the pinned compiler into kernel/work."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request

KERNEL = Path(__file__).resolve().parent
WORK = KERNEL / 'work'
LOCK = json.loads((KERNEL / 'sources.lock.json').read_text())


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source(name, spec):
    """Use the platform-prepared submodule; never fetch or change its revision."""
    target = KERNEL / spec['submodule']
    if not (target / '.git').exists():
        raise RuntimeError('Missing kernel submodule; run git submodule update --init --recursive')
    top = run('git', '-C', target, 'rev-parse', '--show-toplevel',
              capture_output=True, text=True).stdout.strip()
    if Path(top).resolve() != target.resolve():
        raise RuntimeError(f'Not an initialized source submodule: {target}')
    actual = run('git', '-C', target, 'rev-parse', 'HEAD', capture_output=True, text=True).stdout.strip()
    if actual != spec['commit']:
        raise RuntimeError(f'Source commit mismatch: {name}; update the pinned submodule')
    for path in spec.get('paths', []):
        if not (target / path).is_dir():
            raise RuntimeError(f'Missing selected source directory: {name}/{path}')
    return target


def toolchain():
    spec = LOCK['toolchain']
    target = WORK / 'toolchains' / spec['directory']
    archive = WORK / 'downloads' / (spec['directory'] + '.tar.xz')
    archive.parent.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        try:
            with urllib.request.urlopen(spec['url'], timeout=120) as source, partial.open('xb') as out:
                while block := source.read(8 * 1024**2):
                    out.write(block)
            if sha256(partial) != spec['sha256']:
                raise RuntimeError('Toolchain download SHA256 mismatch')
            partial.replace(archive)
        finally:
            partial.unlink(missing_ok=True)
    if sha256(archive) != spec['sha256']:
        raise RuntimeError('Toolchain archive SHA256 mismatch')
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        # Debian 12's original Python 3.11 lacks tarfile extraction filters.
        # Use GNU tar only after the pinned archive's SHA256 check, preserving
        # compiler executable bits and internal links without adopting owners.
        # Publish only a complete extraction, so failures are safe to retry.
        with tempfile.TemporaryDirectory(dir=target.parent, prefix='.extract-') as temporary:
            run('tar', '--extract', '--xz', '--file', archive,
                '--directory', temporary, '--no-same-owner')
            extracted = Path(temporary) / spec['directory']
            if not (extracted / 'bin' / (spec['prefix'] + 'gcc')).is_file():
                raise RuntimeError('Toolchain archive is missing its compiler')
            extracted.rename(target)
    compiler = target / 'bin' / (spec['prefix'] + 'gcc')
    run(compiler, '--version')


def main():
    WORK.mkdir(exist_ok=True)
    config = LOCK['base_config']
    if sha256(KERNEL / config['path']) != config['sha256']:
        raise RuntimeError('Vendor baseline configuration SHA256 mismatch')
    source('linux', LOCK['linux'])
    source('components', LOCK['components'])
    toolchain()
    print('Pinned kernel submodules verified; compiler ready under kernel/work/')


if __name__ == '__main__':
    main()
