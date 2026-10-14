#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Finite boot, Mali and Codec2 checks; never restarts an instance."""
import argparse
import json
from pathlib import Path
import subprocess
import time
from common import ROOT,WORK,run

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name',default='redroid')
args=parser.parse_args()
name=args.name
for _ in range(90):
    result=subprocess.run(['docker','exec',name,'/system/bin/getprop','sys.boot_completed'],capture_output=True)
    if result.returncode==0 and result.stdout.strip()==b'1':break
    time.sleep(2)
else:raise RuntimeError('Android not ready in 180 seconds; no automatic restart performed')
info=json.loads(run('docker','inspect',name,capture_output=True).stdout)[0]
fps=next((int(a.split('=',1)[1]) for a in info['Config']['Cmd'] if a.startswith('androidboot.redroid_fps=')),120)
# boot_completed and the exec_background refresh-policy hook are asynchronous.
for _ in range(15):
    policy=run('docker','exec',name,'sh','-c',
        'settings get system peak_refresh_rate; settings get system min_refresh_rate',capture_output=True).stdout.decode().splitlines()
    if len(policy)==2 and all(v in (str(fps),f'{fps}.0') for v in policy):break
    time.sleep(1)
else:raise RuntimeError('Refresh policy hook did not converge to the configured display rate')
state=run('docker','exec',name,'sh','-c',
    'getprop ro.hardware.egl; getprop ro.hardware.vulkan; '
    'getprop init.svc.android-hardware-media-c2-cix-hal-1-0; '
    'wm size; settings get system peak_refresh_rate; settings get system min_refresh_rate; '
    'dumpsys SurfaceFlinger | grep -E "GLES:|activeMode="',capture_output=True).stdout.decode()
assert len(info['Mounts'])==1 and info['Mounts'][0]['Type']=='bind' and info['Mounts'][0]['Destination']=='/data'
assert Path(info['Mounts'][0]['Source']).resolve().is_relative_to(ROOT.resolve())
assert not info['Config'].get('Volumes')
if state.splitlines()[:3]!=['mali','mali','running'] or 'Mali' not in state:
    raise RuntimeError('Unexpected graphics/Codec2 state: '+state)
(WORK/('runtime-'+name+'.json')).write_text(json.dumps({'id':info['Id'],'state':state,
    'mounts':info['Mounts'],'port_bindings':info['HostConfig']['PortBindings']},indent=2)+'\n')
print(state)
print('Boot/Mali/Codec2 registration passed; this alone is not a video encode or long-stability test.')
