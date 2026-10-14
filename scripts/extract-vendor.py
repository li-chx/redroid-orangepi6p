#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read a pinned official .7z/.img; extract vendor without mounts or device writes."""
import argparse
from pathlib import Path
import subprocess
from common import WORK,LOCK,checked,run
from image_gpt import inspect
from image_super import parse

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('input',type=Path)
args=parser.parse_args()
source=args.input.resolve(); directory=WORK/'extract';directory.mkdir(exist_ok=True)
if source.suffix=='.7z':
    checked(source,LOCK['archive_sha256'])
    image=directory/'factory.img'
    if not image.exists():
        with image.open('wb') as output:
            run('7z','x','-so',source,'Orangepi6plus_1.0.1_android14_linux6.1.44.img',stdout=output)
else:image=source
checked(image,LOCK['image_sha256'])
gpt=inspect(image)
superpart=next(p for p in gpt['partitions'] if p['name']=='super')
if not superpart['complete_in_file']:raise RuntimeError('Truncated super partition')
vendor_image=directory/'vendor.img'
with image.open('rb') as stream:
    metadata=parse(stream,superpart['offset'],superpart['bytes'])
    partition=next(p for p in metadata['partitions'] if p['name'] in ('vendor','vendor_a'))
    if vendor_image.exists():raise RuntimeError('Remove only work/extract/vendor.img before re-extracting')
    with vendor_image.open('xb') as output:
        for extent in partition['extents']:
            stream.seek(superpart['offset']+extent['super_offset'])
            remaining=extent['bytes']
            while remaining:
                size=min(remaining,8*1024**2)
                data=stream.read(size) if extent['kind']==0 else bytes(size)
                if len(data)!=size:raise RuntimeError('Truncated extent')
                output.write(data);remaining-=size
vendor=directory/'vendor'
if vendor.exists():raise RuntimeError('Vendor output already exists; choose existing directory for prepare.py')
vendor.mkdir()
quoted=str(vendor).replace('\\','\\\\').replace('"','\\"')
run('debugfs','-R',f'rdump / "{quoted}"',vendor_image)
print('Extracted vendor directory:',vendor)
print('Next: python3 scripts/prepare.py --vendor-dir',vendor)
