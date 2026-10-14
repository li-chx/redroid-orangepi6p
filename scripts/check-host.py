#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only host prerequisites; does not install modules or change boot settings."""
import gzip
import json
import platform
from pathlib import Path
import sys

required=['CONFIG_ANDROID_BINDER_IPC','CONFIG_ANDROID_BINDERFS','CONFIG_MEMFD_CREATE',
          'CONFIG_IP_ADVANCED_ROUTER','CONFIG_IP_MULTIPLE_TABLES','CONFIG_IPV6_MULTIPLE_TABLES',
          'CONFIG_FIB_RULES','CONFIG_NAMESPACES','CONFIG_CGROUPS']
config=Path('/proc/config.gz')
values={}
if config.is_file():
    for line in gzip.decompress(config.read_bytes()).decode().splitlines():
        if line.startswith('CONFIG_') and '=' in line:
            k,v=line.split('=',1);values[k]=v
nodes={str(f):f.exists() for f in map(Path,('/dev/mali0','/dev/video1'))}
drivers={name:[f.name for f in Path('/sys/bus/platform/drivers/'+name).glob('CIXH*')]
         for name in ('mali','amvx_dev')}
report={'machine':platform.machine(),'kernel':platform.release(),'nodes':nodes,
        'bound_devices':drivers,'config':{k:values.get(k,'unknown') for k in required}}
print(json.dumps(report,indent=2))
if platform.machine()!='aarch64' or not all(nodes.values()) or not all(drivers.values()):
    sys.exit('Requires a real CIX/Mali/amvx ARM64 host; see kernel/README.md')
if values and any(values.get(k) not in ('y','m') for k in required):
    sys.exit('Missing kernel prerequisites; no host changes made')
if not values:print('Kernel config unreadable: Binder/routing requirements still need verification',file=sys.stderr)
