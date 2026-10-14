#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Functional video test ONLY on a fresh, empty instance, with project-local outputs."""
import argparse
import json
import subprocess
import time
from pathlib import Path
from common import ROOT,WORK,run

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--name',required=True)
parser.add_argument('--fresh-test-instance',action='store_true',required=True,
                    help='confirm this is a disposable test instance: navigates HOME/Settings')
args=parser.parse_args();name=args.name
run('python3',ROOT/'scripts/check-runtime.py','--name',name)
out=WORK/'verification'/name;out.mkdir(parents=True,exist_ok=True)
run('docker','exec',name,'am','start','-W','-a','android.settings.SETTINGS')
with (out/'screenrecord.txt').open('wb') as log:
    encoder=subprocess.Popen(['docker','exec',name,'screenrecord','--verbose','--codec-name',
        'c2.cix.avc.encoder','--size','1920x1080','--bit-rate','8000000','--time-limit','8',
        '--output-format=h264','/data/firstboot-cix.h264'],stdout=log,stderr=subprocess.STDOUT)
    try:
        time.sleep(2)
        live=run('docker','exec',name,'sh','-c',
            'for p in $(pidof android.hardware.media.c2@1.0-cix-service); do '
            'echo PID=$p; ls -l /proc/$p/fd | grep -E "video|dma_heap"; done',capture_output=True).stdout
        (out/'encoder-live-fd.txt').write_bytes(live)
        for _ in range(2):
            run('docker','exec',name,'input','keyevent','3')
            run('docker','exec',name,'am','start','-W','-a','android.settings.SETTINGS')
        rc=encoder.wait(timeout=25)
    finally:
        if encoder.poll() is None:encoder.terminate();encoder.wait(timeout=5)
if rc:raise RuntimeError('Hardware screenrecord failed; see retained log')
video=out/'firstboot-cix.h264'
run('docker','cp',name+':/data/firstboot-cix.h264',video)
probe=run('ffprobe','-v','error','-count_frames','-show_entries',
    'stream=codec_name,width,height,nb_read_frames','-of','json',video,capture_output=True)
(out/'video-info.json').write_bytes(probe.stdout)
with (out/'decode.txt').open('wb') as log:
    run('ffmpeg','-nostdin','-v','error','-i',video,'-f','null','-',stdout=log,stderr=subprocess.STDOUT)
snapshot=run('docker','exec',name,'screencap','-p',capture_output=True).stdout
(out/'settings.png').write_bytes(snapshot)
vulkan=run('docker','exec',name,'cmd','gpu','vkjson',capture_output=True).stdout
(out/'vkjson.txt').write_bytes(vulkan)
assert b'/dev/video1' in live and b'Mali' in vulkan
print(probe.stdout.decode())
print('Fresh-instance 1080p CIX hardware screen recording and complete decode passed.')
print('This is a functional test, not a sustained FPS, latency, or game benchmark.')
