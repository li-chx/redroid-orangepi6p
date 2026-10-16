# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
LOCK = json.loads((ROOT/'config/inputs.lock.json').read_text())
WORK.mkdir(exist_ok=True)
(WORK/'tmp').mkdir(exist_ok=True)
os.environ['TMPDIR'] = str(WORK/'tmp')

def run(*args, **kwargs):
    return subprocess.run([str(a) for a in args], check=True, **kwargs)

def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8*1024**2), b''):
            h.update(block)
    return h.hexdigest()

def checked(path, expected):
    if digest(path) != expected:
        raise RuntimeError(f'Input SHA256 mismatch: {path}')

def image_info(ref):
    result = run('docker', 'image', 'inspect', ref, capture_output=True)
    return json.loads(result.stdout)[0]

def base_image(ref):
    result = subprocess.run(['docker','image','inspect',ref], capture_output=True)
    if result.returncode:
        run('docker','pull','--platform=linux/arm64',ref)
    info = image_info(ref)
    # Classic stores identify an image by its config digest. Docker's containerd
    # store can report the manifest digest instead; both identify this pinned
    # baseline. Keep the platform and implicit-volume checks in either case.
    expected_ids = {LOCK['base_image_id'], LOCK['base_image'].rsplit('@', 1)[1]}
    if info['Id'] not in expected_ids or info['Architecture'] != 'arm64' or info['Config'].get('Volumes'):
        raise RuntimeError('Base image differs from the pinned, volume-free ARM64 baseline')
    return info
