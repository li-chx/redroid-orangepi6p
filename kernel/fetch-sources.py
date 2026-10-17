#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the CNB vendor snapshot and fetch the pinned compiler into kernel/work."""
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


def snapshot():
    """Require the initialized, pinned vendor submodule; never fetch or reset it."""
    spec = LOCK['snapshot']
    root = KERNEL / spec['submodule']
    if not (root / '.git').exists():
        raise RuntimeError('Missing kernel submodule; run git submodule update --init --recursive')
    top = run('git', '-C', root, 'rev-parse', '--show-toplevel',
              capture_output=True, text=True).stdout.strip()
    if Path(top).resolve() != root.resolve():
        raise RuntimeError(f'Not an initialized source submodule: {root}')
    actual = run('git', '-C', root, 'rev-parse', 'HEAD', capture_output=True, text=True).stdout.strip()
    if actual != spec['commit']:
        raise RuntimeError('Source snapshot commit mismatch; update the pinned submodule')
    run('git', '-C', root, 'diff', '--no-ext-diff', '--no-textconv',
        '--exit-code', 'HEAD', '--', spec['manifest'])
    return root


def source(name, spec):
    """Verify source provenance and exact committed trees inside the vendor snapshot."""
    root = snapshot()
    target = KERNEL / spec['directory']
    relative = target.relative_to(root)
    if not target.is_dir():
        raise RuntimeError(f'Missing source directory: {name}')
    manifest = json.loads((root / LOCK['snapshot']['manifest']).read_text())
    origin = manifest[name]
    if origin['commit'] != spec['commit'] or origin['url'] != spec['url']:
        raise RuntimeError(f'Source provenance mismatch: {name}')
    paths = spec.get('paths', [])
    for path in paths:
        if not (target / path).is_dir():
            raise RuntimeError(f'Missing selected source directory: {name}/{path}')
    expected = {'.': spec['tree']} if 'tree' in spec else spec['trees']
    for path, tree in expected.items():
        subtree = (relative / path).as_posix()
        actual = run('git', '-C', root, 'rev-parse', f'HEAD:{subtree}',
                     capture_output=True, text=True).stdout.strip()
        if actual != tree:
            raise RuntimeError(f'Source tree mismatch: {name}/{path}')
    if paths:
        run('git', '-C', target, 'diff', '--no-ext-diff', '--no-textconv',
            '--exit-code', 'HEAD', '--', *paths)
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
    print('Pinned CNB vendor snapshot verified; compiler ready under kernel/work/')


if __name__ == '__main__':
    main()
