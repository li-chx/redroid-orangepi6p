#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Launch a fresh project-bound instance; never replaces or stops another container."""
import argparse
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from common import ROOT,WORK,run,image_info

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--image',default='orangepi6p-redroid:14-gpu-vpu')
parser.add_argument('--name',default='redroid')
parser.add_argument('--bind',default='127.0.0.1',help='ADB listen IPv4; LAN use must be explicit')
parser.add_argument('--port',type=int,default=5555)
parser.add_argument('--width',type=int,default=1920)
parser.add_argument('--height',type=int,default=1080)
parser.add_argument('--fps',type=int,default=120,help='virtual display target, not guaranteed game/stream fps')
parser.add_argument('--dpi',type=int,default=160)
args=parser.parse_args()
if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]{0,63}',args.name):parser.error('Invalid container name')
if not isinstance(ipaddress.ip_address(args.bind),ipaddress.IPv4Address):parser.error('Use IPv4')
if not (1<=args.port<=65535 and 1<=args.width<=8192 and 1<=args.height<=8192 and 1<=args.fps<=240 and 72<=args.dpi<=1000):parser.error('Invalid display/port values')
run(sys.executable,ROOT/'scripts/check-host.py')
if subprocess.run(['docker','inspect',args.name],capture_output=True).returncode==0:
    raise RuntimeError('Container name already exists; use docker start or choose another name. Nothing stopped.')
info=image_info(args.image)
if info['Config'].get('Volumes') or info['Architecture']!='arm64':raise RuntimeError('Unexpected image/implicit volumes')
data=ROOT/'data'/args.name
if not data.resolve().is_relative_to(ROOT.resolve()):raise RuntimeError('Data path escapes this project')
data.mkdir(parents=True,exist_ok=True)
stats=data/'gpu-mapper5-stats'
stats.mkdir(mode=0o700,exist_ok=True)
if not stats.resolve().is_relative_to(data.resolve()):raise RuntimeError('Stats path escapes application data')
if stats.stat().st_uid==os.geteuid():stats.chmod(0o700)
else:run('sudo','chmod','700',stats)
if stats.stat().st_uid!=1000:
    run('sudo','chown','1000:1000',stats)
cmd=['docker','run','-d','--name',args.name,'--privileged','--restart=no','--pull=never',
     '--mount',f'type=bind,src={data.resolve()},dst=/data',
     '-p',f'{args.bind}:{args.port}:5555',args.image,
     'androidboot.use_memfd=1','androidboot.redroid_gpu_mode=guest',
     f'androidboot.redroid_width={args.width}',f'androidboot.redroid_height={args.height}',
     f'androidboot.redroid_fps={args.fps}',f'androidboot.redroid_dpi={args.dpi}']
(WORK/('run-'+args.name+'.json')).write_text(json.dumps(cmd,indent=2)+'\n')
run(*cmd)
print(f'ADB endpoint {args.bind}:{args.port}; only /data is bind-mounted at {data}')
