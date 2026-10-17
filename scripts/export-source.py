#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create a source-only archive using a whitelist, never a workspace-wide copy."""
import gzip
import hashlib
import io
import os
import re
from pathlib import Path
import tarfile
from common import ROOT

allowed=['.gitmodules','README.md','LICENSE','NOTICE','Dockerfile','.dockerignore','.gitignore','.gitattributes',
         'src','scripts','config','docs','kernel','LICENSES','.ci','.cnb','.cnb.yml']
files=[]
for name in allowed:
    path=ROOT/name
    if not path.exists():raise RuntimeError('Missing release entry: '+name)
    if path.is_file():
        files.append(path)
    else:
        for directory, folders, names in os.walk(path, followlinks=False):
            folders[:] = [name for name in folders if name not in ('.git', '__pycache__')
                          and Path(directory, name).relative_to(ROOT).parts[:2]
                          not in (('kernel', 'work'), ('kernel', 'upstream'), ('kernel', 'vendor-snapshot'))]
            files.extend(Path(directory, name) for name in names)
files=sorted(f for f in files if '__pycache__' not in f.parts and f.suffix!='.pyc'
             and f.relative_to(ROOT).parts[:2]!=('kernel','work'))
for f in files:
    if f.is_symlink() or f.suffix in ('.so','.o','.img','.apk','.7z','.tar'):
        raise RuntimeError('Unexpected non-source release entry: '+str(f))
    data=f.read_bytes()
    if any(re.search(pattern,data) for pattern in (
        rb'\b192\.168\.\d{1,3}\.\d{1,3}\b',rb'/home/[A-Za-z0-9_.-]+/',
        rb'-----BEGIN [A-Z ]*PRIVATE KEY-----')):
        raise RuntimeError('Private workspace material detected: '+str(f))
out=ROOT/'dist';out.mkdir(exist_ok=True)
archive=out/'orangepi6p-redroid-source.tar.gz'
manifest=''.join(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(ROOT))+'\n' for f in files).encode()
with archive.open('wb') as raw,gzip.GzipFile(fileobj=raw,mode='wb',mtime=0,filename='') as zipped,tarfile.open(fileobj=zipped,mode='w') as tar:
    for name,data in [(str(f.relative_to(ROOT)),f.read_bytes()) for f in files]+[('SOURCE-SHA256SUMS',manifest)]:
        item=tarfile.TarInfo('orangepi6p-redroid/'+name)
        item.size=len(data);item.mode=0o644;item.mtime=0
        tar.addfile(item,io.BytesIO(data))
print(f'Source-only archive: {archive} ({archive.stat().st_size} bytes, {len(files)} source files)')
