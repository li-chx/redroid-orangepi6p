#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a local image, checking the baseline and recording the exact payload."""
import argparse
import json
import os
import shutil
from common import ROOT,WORK,LOCK,run,base_image,image_info,digest

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-image',default=LOCK['base_image'])
parser.add_argument('--tag',default='orangepi6p-redroid:14')
args=parser.parse_args()
base_image(args.base_image)
rootfs=WORK/'rootfs'
if not (rootfs/'vendor/lib64/android.hardware.graphics.composer@2.1-resources.so').is_file():
    raise RuntimeError('Run prepare.py and build-resources.py first')
# Registry consumers receive the component notices with the image itself.
notices=rootfs/'vendor/etc/orangepi6p-redroid'
notices.mkdir(parents=True,exist_ok=True)
for name in ['LICENSE','NOTICE']:
    shutil.copyfile(ROOT/name,notices/name)
shutil.copytree(ROOT/'LICENSES',notices/'LICENSES',dirs_exist_ok=True)
manifest=[{'path':str(f.relative_to(rootfs)),'bytes':f.stat().st_size,'sha256':digest(f)}
          for f in sorted(rootfs.rglob('*')) if f.is_file()]
(WORK/'payload-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
env=dict(os.environ)
# The build has no RUN steps; legacy mode also works on hosts without buildx.
env['DOCKER_BUILDKIT']='0'
# Whitelist the context independently of .dockerignore: no caches, factory image,
# application data, or source checkout can accidentally be sent to Docker.
context=WORK/'docker-context'
if context.exists():shutil.rmtree(context)
context.mkdir()
shutil.copyfile(ROOT/'Dockerfile',context/'Dockerfile')
shutil.copytree(rootfs,context/'work/rootfs')
try:
    run('docker','build','--pull=false','--network=none','--platform=linux/arm64',
        '--build-arg','BASE_IMAGE='+args.base_image,
        '--build-arg','SOURCE_REVISION='+os.environ.get('CNB_COMMIT','local'),
        '-t',args.tag,context,env=env)
finally:
    shutil.rmtree(context)
info=image_info(args.tag)
if info['Config'].get('Volumes') or info['Architecture']!='arm64':
    raise RuntimeError('Unexpected image platform or implicit volumes')
(WORK/'image-result.json').write_text(json.dumps({'tag':args.tag,'id':info['Id'],
    'base':LOCK['base_image_id'],'payload_files':len(manifest),
    'payload_bytes':sum(f['bytes'] for f in manifest)},indent=2)+'\n')
print('Local image ready:',info['Id'],'(not pushed)')
