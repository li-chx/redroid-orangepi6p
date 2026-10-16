#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch pinned kernel inputs into kernel/work; never install anything on the host."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import urllib.request

KERNEL = Path(__file__).resolve().parent
WORK = KERNEL / 'work'
LOCK = json.loads((KERNEL / 'sources.lock.json').read_text())


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def checkout(name, spec):
    target = WORK / 'sources' / name
    if not target.exists():
        target.mkdir(parents=True)
        run('git', '-C', target, 'init', '--quiet')
        run('git', '-C', target, 'remote', 'add', 'origin', spec['url'])
    if not (target / '.git').is_dir():
        raise RuntimeError(f'Not an isolated source checkout: {target}')
    head = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    if head.returncode or head.stdout.strip() != spec['commit']:
        if head.returncode == 0:
            raise RuntimeError(f'Existing checkout has a different commit: {target}')
        run('git', '-C', target, 'fetch', '--depth=1', '--filter=blob:none', 'origin', spec['commit'])
        if spec.get('paths'):
            run('git', '-C', target, 'sparse-checkout', 'init', '--cone')
            run('git', '-C', target, 'sparse-checkout', 'set', *spec['paths'])
        run('git', '-C', target, 'checkout', '--detach', spec['commit'])
    actual = run('git', '-C', target, 'rev-parse', 'HEAD', capture_output=True, text=True).stdout.strip()
    if actual != spec['commit']:
        raise RuntimeError(f'Source commit mismatch: {name}')
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
        with tarfile.open(archive) as source:
            # Python's data filter checks paths, ownership and symlink targets.
            source.extractall(target.parent, filter='data')
    compiler = target / 'bin' / (spec['prefix'] + 'gcc')
    run(compiler, '--version')


def main():
    WORK.mkdir(exist_ok=True)
    config = LOCK['base_config']
    if sha256(KERNEL / config['path']) != config['sha256']:
        raise RuntimeError('Vendor baseline configuration SHA256 mismatch')
    checkout('linux', LOCK['linux'])
    checkout('components', LOCK['components'])
    toolchain()
    print('Pinned kernel sources and compiler ready under kernel/work/')


if __name__ == '__main__':
    main()
