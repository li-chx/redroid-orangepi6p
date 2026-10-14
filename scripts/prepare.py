#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import verified local factory inputs and the pinned base; no host installation."""
import argparse
import json
import os
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from common import ROOT, WORK, LOCK, checked, base_image, run

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--vendor-dir', type=Path, required=True, help='extracted official vendor/ directory')
parser.add_argument('--base-rootfs', type=Path, help='optional already-extracted pinned base, otherwise use Docker')
parser.add_argument('--base-image', default=LOCK['base_image'])
args = parser.parse_args()
vendor = args.vendor_dir.resolve()
for item in LOCK['vendor_files']:
    source = (vendor/item['source'].removeprefix('vendor/')).resolve()
    if not source.is_relative_to(vendor):
        raise RuntimeError('Factory input escapes vendor directory')
    checked(source, item['sha256'])
base = WORK/'base'
base.mkdir(exist_ok=True)
container = None
try:
    if args.base_rootfs is None:
        base_image(args.base_image)
        container = run('docker','create','--network=none',args.base_image,capture_output=True).stdout.decode().strip()
    for item in LOCK['base_files']:
        target = base/item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        if container:
            run('docker','cp','-L',container+':/'+item['path'],target)
        else:
            shutil.copyfile(args.base_rootfs/item['path'],target)
        checked(target,item['sha256'])
finally:
    if container:
        run('docker','rm',container)

rootfs = WORK/'rootfs'
if rootfs.exists():
    shutil.rmtree(rootfs)  # generated payload only; never application data
rootfs.mkdir()
for item in LOCK['vendor_files']:
    target = rootfs/item['target']
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(vendor/item['source'].removeprefix('vendor/'),target)
    target.chmod(0o755 if '/bin/' in item['target'] else 0o644)
    if target.name in ('manifest_allocator.xml','mapper.arm.xml'):
        tree = ET.parse(target)
        tree.getroot().set('version','7.0')
        tree.write(target,encoding='utf-8',xml_declaration=True)
    if target.name == 'android.hardware.graphics.allocator-V2-service.rc':
        target.write_text(target.read_text().replace('    onrestart restart surfaceflinger\n',''))

manifest = ET.parse(base/'vendor/etc/vintf/manifest.xml')
for child in list(manifest.getroot()):
    if child.tag == 'hal' and child.findtext('name') in ('android.hardware.graphics.allocator','android.hardware.graphics.mapper'):
        manifest.getroot().remove(child)
manifest.write(rootfs/'vendor/etc/vintf/manifest.xml',encoding='utf-8',xml_declaration=True)
(rootfs/'vendor/etc/init/android.hardware.graphics.allocator@2.0-service.rc').write_text('# Replaced by Arm AIDL allocator V2.\n')
for source,target in [
    ('gpu_config.sh','vendor/bin/gpu_config.sh'),
    ('cix-codec.rc','vendor/etc/init/android.hardware.media.c2@1.0-cix-service.rc'),
    ('cix-media-c2.xml','vendor/etc/vintf/manifest/cix-media-c2.xml'),
    ('redroid6p.rc','vendor/etc/init/redroid6p.rc'),
    ('redroid6p-ready.sh','vendor/bin/redroid6p-ready.sh'),
]:
    dest=rootfs/target
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'config'/source,dest)
    dest.chmod(0o755 if '/bin/' in target else 0o644)
(WORK/'import-report.json').write_text(json.dumps({'base_image_id':LOCK['base_image_id'],
    'vendor_archive':LOCK['vendor_archive'],'verified_factory_files':len(LOCK['vendor_files'])},indent=2)+'\n')
print('Verified factory payload staged. Next: build-resources.py, then image.py')
