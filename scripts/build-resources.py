#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild the fixed-image mapper5 ComposerResources ABI from source."""
import argparse
import platform
import shutil
from common import ROOT,WORK,run,digest

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cxx',default='clang++')
parser.add_argument('--ld',default='ld' if platform.machine()=='aarch64' else 'aarch64-linux-gnu-ld')
args=parser.parse_args()
headers=WORK/'headers'; base=WORK/'base/system'
for f in [headers/'libcxx/vector',base/'lib64/libc++.so']:
    if not f.is_file():raise RuntimeError('Run prepare.py and fetch-headers.py first')
obj=WORK/'resources.o'
run(args.cxx,'--target=aarch64-linux-android34','-std=c++17','-fno-exceptions','-fno-rtti','-O2','-fPIC',
    '-fno-stack-protector','-mno-outline-atomics','-nostdinc++','-Wall','-Wextra','-Werror',
    '-Wno-tautological-unsigned-zero-compare','-Wno-deprecated-builtins',
    '-isystem',headers/'libcxx','-isystem',headers/'bionic','-isystem',headers/'kernel-android/uapi',
    '-isystem',headers/'kernel-uapi/asm-arm64','-isystem',headers/'kernel-uapi',
    '-I'+str(ROOT/'src/include'),'-I'+str(ROOT/'src'),'-c',ROOT/'src/ComposerResources.cpp','-o',obj)
output=WORK/'rootfs/vendor/lib64/android.hardware.graphics.composer@2.1-resources.so'
output.parent.mkdir(parents=True,exist_ok=True)
run(args.ld,'-shared','--hash-style=both','-z','noexecstack','--allow-shlib-undefined',
    '-soname',output.name,'-o',output,obj,
    base/'lib64/libc++.so',base/'lib64/libcutils.so',base/'lib64/libvndksupport.so',base/'lib64/liblog.so',
    base/'apex/com.android.runtime/lib64/bionic/libc.so',base/'apex/com.android.runtime/lib64/bionic/libdl.so')
print('Built mapper5 resource library:',digest(output))
