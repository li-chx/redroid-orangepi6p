#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch pinned kernel inputs into kernel/work; never install anything on the host."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import urllib.request

KERNEL = Path(__file__).resolve().parent
WORK = KERNEL / 'work'
LOCK = json.loads((KERNEL / 'sources.lock.json').read_text())


def run(*args, **kwargs):
    return subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def network_git(target, *args):
    # Public inputs need no interactive login. Retry both explicit fetches and
    # checkout/sparse-checkout, which can fetch missing blobs themselves.
    for attempt in range(3):
        try:
            return run('git', '-C', target, *args,
                       env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            print(f'Git {args[0]} failed; retry {attempt + 2}/3', flush=True)
            time.sleep(2 ** (attempt + 1))


def checkout(name, spec):
    target = WORK / 'sources' / name
    if not target.exists():
        target.mkdir(parents=True)
        run('git', '-C', target, 'init', '--quiet')
        run('git', '-C', target, 'remote', 'add', 'origin', spec['url'])
    if not (target / '.git').is_dir():
        raise RuntimeError(f'Not an isolated source checkout: {target}')
    run('git', '-C', target, 'remote', 'set-url', 'origin', spec['url'])
    head = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    if head.returncode == 0 and head.stdout.strip() != spec['commit']:
        raise RuntimeError(f'Existing checkout has a different commit: {target}')
    partial = subprocess.run(['git', '-C', str(target), 'config', '--bool', '--get',
                              'remote.origin.promisor'], capture_output=True, text=True)
    complete_linux = not spec.get('paths') and partial.stdout.strip() == 'true'
    if head.returncode or complete_linux:
        # Linux needs every file in the selected commit; blob filtering only
        # postpones that same download until checkout. Components stay sparse.
        options = ['--filter=blob:none'] if spec.get('paths') else ['--no-filter']
        if complete_linux:
            options.append('--refetch')  # Fill even an interrupted partial cache.
        network_git(target, 'fetch', '--depth=1', *options, 'origin', spec['commit'])
        if complete_linux:
            run('git', '-C', target, 'config', 'remote.origin.promisor', 'false')
            cleared = subprocess.run(['git', '-C', str(target), 'config', '--unset-all',
                                      'remote.origin.partialclonefilter'])
            if cleared.returncode not in (0, 5):
                cleared.check_returncode()
    if spec.get('paths'):
        if head.returncode:
            run('git', '-C', target, 'sparse-checkout', 'init', '--cone')
        network_git(target, 'sparse-checkout', 'set', *spec['paths'])
    # HEAD may already exist after an interrupted checkout; still finish it.
    # Without --force this preserves the deliberate build patch on cache reuse.
    network_git(target, 'checkout', '--detach', spec['commit'])
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
    checkout('linux', LOCK['linux'])
    checkout('components', LOCK['components'])
    toolchain()
    print('Pinned kernel sources and compiler ready under kernel/work/')


if __name__ == '__main__':
    main()
