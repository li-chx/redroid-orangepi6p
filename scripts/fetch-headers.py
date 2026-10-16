#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fetch pinned Android14 build headers; cache and outputs stay under work/."""
import base64
import json
from pathlib import Path
import tarfile
import urllib.request
from common import ROOT, WORK, checked

for item in json.loads((ROOT/'config/header-sources.json').read_text()):
    cache = WORK/'cache'/item['file']
    cache.parent.mkdir(parents=True, exist_ok=True)
    if not cache.exists():
        data = urllib.request.urlopen(item['url'], timeout=90).read()
        if item['url'].endswith('format=TEXT'):
            data = base64.b64decode(data)
        cache.write_bytes(data)
    checked(cache, item['sha256'])
    if item['file'].endswith('.tar.gz'):
        out = WORK/'headers'/item['file'][:-7]
        out.mkdir(parents=True, exist_ok=True)
        with tarfile.open(cache) as archive:
            # Upstream libcxx contains a link outside the include subtree;
            # only regular files/directories are used and that header is pinned separately.
            for member in archive.getmembers():
                if not (member.isfile() or member.isdir()):
                    continue
                dest = (out/member.name).resolve()
                if not dest.is_relative_to(out.resolve()):
                    raise RuntimeError('Unsafe header archive member')
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    dest.write_bytes(archive.extractfile(member).read())
    else:
        target = WORK/'headers/libcxx'/item['file']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(cache.read_bytes())
print('Pinned Android14 headers ready under work/headers')
