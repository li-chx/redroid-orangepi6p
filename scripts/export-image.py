#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the freshly built Docker image with matching source, notices and hashes."""
import gzip
import json
import os
import shutil
import subprocess

from common import ROOT, WORK, digest, image_info


IMAGE = 'orangepi6p-redroid:14'


def save_image(image, destination):
    partial = destination.with_suffix(destination.suffix + '.partial')
    if partial.exists():
        raise RuntimeError('A partial image export already exists')
    try:
        with partial.open('xb') as raw:
            process = subprocess.Popen(['docker', 'image', 'save', image], stdout=subprocess.PIPE)
            try:
                with process.stdout, gzip.GzipFile(fileobj=raw, mode='wb', mtime=0, filename='') as zipped:
                    shutil.copyfileobj(process.stdout, zipped)
                if process.wait():
                    raise RuntimeError('docker image save failed')
            except BaseException:
                if process.poll() is None:
                    process.terminate()
                process.wait()
                raise
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def main():
    result = json.loads((WORK / 'image-result.json').read_text())
    info = image_info(IMAGE)
    if (result['tag'] != IMAGE or info['Id'] != result['id'] or
            info['Architecture'] != 'arm64' or info['Config'].get('Volumes')):
        raise RuntimeError('Image differs from the just-built, volume-free ARM64 image')
    source = ROOT / 'dist/orangepi6p-redroid-source.tar.gz'
    if not source.is_file():
        raise RuntimeError('Run export-source.py first')
    out = ROOT / 'dist/redroid'
    # Require an empty destination so a previous build cannot leak into the bundle.
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise RuntimeError('dist/redroid must be empty before exporting')
    save_image(IMAGE, out / 'orangepi6p-redroid-14-arm64.tar.gz')
    shutil.copyfile(source, out / source.name)
    for name in ['image-result.json', 'payload-manifest.json', 'import-report.json']:
        shutil.copyfile(WORK / name, out / name)
    shutil.copyfile(ROOT / 'config/inputs.lock.json', out / 'inputs.lock.json')
    for name in ['LICENSE', 'NOTICE']:
        shutil.copyfile(ROOT / name, out / name)
    shutil.copytree(ROOT / 'LICENSES', out / 'LICENSES')
    (out / 'build-info.json').write_text(json.dumps({
        'source_commit': os.environ.get('CNB_COMMIT'),
        'workflow_run': os.environ.get('CNB_BUILD_ID'),
        'image': IMAGE,
        'image_id': result['id'],
        'platform': 'linux/arm64',
        'validation': 'Build only; board runtime not tested by this workflow',
    }, indent=2) + '\n')
    (out / 'INSTALL.txt').write_text('''Orange Pi 6 Plus ReDroid Android 14 (ARM64)

On your Debian ARM64 board, in the directory containing this file:
  sha256sum -c SHA256SUMS
  tar -xzf orangepi6p-redroid-source.tar.gz
  docker load -i orangepi6p-redroid-14-arm64.tar.gz
  cd orangepi6p-redroid
  python3 scripts/check-host.py
  python3 scripts/run.py
  python3 scripts/check-runtime.py

Docker and Python 3 must already be installed. Docker access is required.
This bundle does not install or replace the host kernel. Binder and matching
vendor GPU/VPU drivers must already be available; see kernel/README.md.
For LAN ADB access, use the alternative run.py command in README.md at creation.
Keep data/redroid/ to preserve apps and user data. Existing containers use
docker start redroid instead of run.py.

The source-only archive excludes factory binaries; the Docker image includes
locally imported factory components and the ReDroid base under their own terms.
Read NOTICE and the original notices in the image before redistributing it.
CI build success does not establish board boot, game compatibility or stability.
''')
    (out / 'SHA256SUMS').write_text(''.join(
        digest(path) + '  ' + path.relative_to(out).as_posix() + '\n'
        for path in sorted(out.rglob('*')) if path.is_file()
    ))
    print('Image, source and SHA256SUMS ready under dist/redroid/')


if __name__ == '__main__':
    main()
