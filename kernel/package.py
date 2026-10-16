#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate the staged ARM64 kernel and vendor modules and produce a Debian bundle."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

KERNEL = Path(__file__).resolve().parent
PROJECT = KERNEL.parent
WORK = KERNEL / 'work'
LOCK = json.loads((KERNEL / 'sources.lock.json').read_text())
RELEASE = LOCK['release']
VENDOR_MODULES = ('memory_group_manager.ko', 'protected_memory_allocator.ko', 'mali_kbase.ko',
                  'aipu.ko', 'amvx.ko', 'armcb_isp_v4l2.ko')


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def output(*args):
    return subprocess.check_output([str(arg) for arg in args], text=True).strip()


def verify_stage(stage):
    if any(path.is_symlink() for path in stage.rglob('*')):
        raise RuntimeError('Package stage contains symlinks or build-machine paths')
    image = stage / 'boot' / ('vmlinuz-' + RELEASE)
    with image.open('rb') as stream:
        if stream.read(64)[56:60] != b'ARM\x64':
            raise RuntimeError('Image is not an ARM64 kernel')
    extra = stage / 'lib/modules' / RELEASE / 'extra'
    for name in VENDOR_MODULES:
        if not (extra / name).is_file():
            raise RuntimeError('Missing vendor module: ' + name)
    expected = output('modinfo', '-F', 'vermagic', extra / VENDOR_MODULES[0])
    if expected.split()[0] != RELEASE:
        raise RuntimeError('Wrong vendor module kernel release')
    modules = sorted((stage / 'lib/modules' / RELEASE).rglob('*.ko'))
    for path in modules:
        with path.open('rb') as stream:
            header = stream.read(20)
        if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\xb7\x00':
            raise RuntimeError('Module is not AArch64 ELF64: ' + path.name)
        if output('modinfo', '-F', 'vermagic', path) != expected:
            raise RuntimeError('Module vermagic differs: ' + path.name)
    for name in ['sky1-orangepi-6-plus', 'sky1-orangepi-6-plus-40pin', 'sky1-orangepi-6-plus-40pin-pwm']:
        if not (stage / 'boot' / ('dtb-' + RELEASE) / 'cix' / (name + '.dtb')).is_file():
            raise RuntimeError('Missing board device tree: ' + name)
    return len(modules)


def build_deb(stage, destination, version):
    package = 'linux-image-' + RELEASE
    for command, value in [('pkgname', package), ('version', version)]:
        subprocess.run(['dpkg', '--validate-' + command, value], check=True)
    helper = stage / 'usr/lib/orangepi6p-redroid-kernel'
    helper.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KERNEL / 'debian/boot.py', helper / 'boot.py')
    (stage / 'etc').mkdir(exist_ok=True)
    shutil.copyfile(KERNEL / 'debian/settings.json', stage / 'etc/orangepi6p-redroid-kernel.json')
    doc = stage / 'usr/share/doc' / package
    doc.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(KERNEL / 'README.md', doc / 'README.md')
    shutil.copyfile(PROJECT / 'NOTICE', doc / 'copyright')
    shutil.copyfile(PROJECT / 'LICENSE', doc / 'LICENSE-MIT')
    shutil.copyfile(PROJECT / 'LICENSES/GPL-2.0-only.txt', doc / 'LICENSE-GPL-2.0-only')
    control = stage / 'DEBIAN'
    control.mkdir(exist_ok=True)
    (control / 'control').write_text(f'''Package: {package}
Version: {version}
Section: kernel
Priority: optional
Architecture: arm64
Maintainer: Orange Pi ReDroid contributors <noreply@localhost>
Depends: kmod, python3 (>= 3.11), util-linux, grub-common
Description: Orange Pi 6 Plus ReDroid kernel with vendor modules
 Kernel {RELEASE} with Binder, policy routing and matching GPU/NPU/VPU/ISP modules.
 Registers an EFI GRUB entry on the factory Debian layout and retains factory boot files.
''')
    (control / 'conffiles').write_text('/etc/orangepi6p-redroid-kernel.json\n')
    for name in ['postinst', 'prerm']:
        shutil.copyfile(KERNEL / 'debian' / name, control / name)
        (control / name).chmod(0o755)
    files = sorted(path for path in stage.rglob('*') if path.is_file() and control not in path.parents)
    (control / 'md5sums').write_text(''.join(
        hashlib.md5(path.read_bytes()).hexdigest() + '  ' + path.relative_to(stage).as_posix() + '\n'
        for path in files
    ))
    partial = destination.with_suffix('.deb.partial')
    if destination.exists() or partial.exists():
        raise RuntimeError('Package output already exists; use a fresh output directory')
    subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(partial)], check=True)
    # Verify actual archive bytes, including the boot helper, rather than only the staging tree.
    expected = {path.relative_to(stage).as_posix(): sha256(path) for path in files}
    seen = set()
    process = subprocess.Popen(['dpkg-deb', '--fsys-tarfile', str(partial)], stdout=subprocess.PIPE)
    try:
        with process.stdout, tarfile.open(fileobj=process.stdout, mode='r|') as archive:
            for member in archive:
                if member.isdir():
                    continue
                name = member.name.removeprefix('./')
                if not member.isfile() or name not in expected or name in seen:
                    raise RuntimeError('Unexpected deb archive member: ' + name)
                if hashlib.file_digest(archive.extractfile(member), 'sha256').hexdigest() != expected[name]:
                    raise RuntimeError('Deb archive content mismatch: ' + name)
                seen.add(name)
        if process.wait() or seen != set(expected):
            raise RuntimeError('Incomplete deb archive')
    except BaseException:
        if process.poll() is None:
            process.terminate()
        process.wait()
        raise
    partial.replace(destination)


def source_archive(destination):
    # Ship exact patched kernel sources and the selected open-source driver trees alongside binaries.
    # Compiler binaries, Git credentials/history and generated .ko files are not included.
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', '0'))
    def normalize(member):
        if '.git' in Path(member.name).parts:
            return None
        member.uid = member.gid = 0
        member.uname = member.gname = ''
        member.mtime = epoch
        return member
    with tarfile.open(destination, 'w:xz', preset=1) as archive:
        archive.add(WORK / 'sources/linux', arcname='sources/linux', filter=normalize)
        archive.add(WORK / 'sources/components/cix_opensource', arcname='sources/cix_opensource', filter=normalize)
        for name in ['sources.lock.json', 'redroid.config', 'vendor-o-build.patch', 'configs', 'debian',
                     'fetch-sources.py', 'build.sh', 'package.py', 'README.md']:
            archive.add(KERNEL / name, arcname='build/' + name, filter=normalize)
        archive.add(WORK / 'build/.config', arcname='build/config.final', filter=normalize)


def main():
    stage = WORK / 'stage'
    modules = verify_stage(stage)
    plan = (WORK / 'logs/mali-load-plan.txt').read_text().splitlines()
    names = [Path(line.split()[1]).name for line in plan if line.startswith('insmod ')]
    if not (names.index('memory_group_manager.ko') < names.index('mali_kbase.ko') and
            names.index('protected_memory_allocator.ko') < names.index('mali_kbase.ko')):
        raise RuntimeError('Mali helper modules must load before mali_kbase')
    out = PROJECT / 'dist/kernel'
    out.mkdir(parents=True, exist_ok=True)
    if any(out.iterdir()):
        raise RuntimeError('dist/kernel must be empty before packaging')
    epoch = int(os.environ.get('SOURCE_DATE_EPOCH', datetime.now(timezone.utc).timestamp()))
    stamp = datetime.fromtimestamp(epoch, timezone.utc).strftime('%Y%m%d%H%M%S')
    version = RELEASE + '-1+' + stamp
    deb = out / ('linux-image-' + RELEASE + '_' + version + '_arm64.deb')
    build_deb(stage, deb, version)
    subprocess.run(['python3', str(PROJECT / 'scripts/export-source.py')], check=True)
    shutil.copyfile(PROJECT / 'dist/orangepi6p-redroid-source.tar.gz', out / 'orangepi6p-redroid-source.tar.gz')
    source_archive(out / ('kernel-source-' + RELEASE + '.tar.xz'))
    shutil.copyfile(KERNEL / 'sources.lock.json', out / 'sources.lock.json')
    shutil.copyfile(WORK / 'build/.config', out / 'config.final')
    shutil.copyfile(KERNEL / 'README.md', out / 'README.md')
    shutil.copyfile(PROJECT / 'NOTICE', out / 'NOTICE')
    shutil.copyfile(PROJECT / 'LICENSES/GPL-2.0-only.txt', out / 'LICENSE-GPL-2.0-only')
    (out / 'INSTALL.txt').write_text('''Orange Pi 6 Plus Debian ARM64 kernel: 6.6.89-cix-redroid

In this extracted directory, on the board:
  sha256sum -c SHA256SUMS
  sudo apt install ./linux-image-6.6.89-cix-redroid_*_arm64.deb

The package registers and selects a GRUB entry on the supported factory EFI
layout. It retains the factory Image/menu and does not reboot automatically.
After reboot, check uname -r before starting ReDroid. If needed, select the
factory kernel from the boot menu. Do not uninstall a currently running kernel.

Only the factory Debian ACPI, no-initrd, same-disk FAT EFI layout is supported.
Registration failure is an installation error, not a successful boot setup.
Configuration: /etc/orangepi6p-redroid-kernel.json
Backups: /var/lib/orangepi6p-redroid-kernel/

kernel-source-6.6.89-cix-redroid.tar.xz contains the corresponding patched Linux,
open-source drivers, final configuration and build scripts under upstream terms.
orangepi6p-redroid-source.tar.gz contains the project source and documentation.
Read NOTICE and README.md for the component licenses and build/runtime scope.
''')
    (out / 'build-info.json').write_text(json.dumps({
        'release': RELEASE, 'deb_version': version, 'module_count': modules,
        'source_commit': os.environ.get('CNB_COMMIT'), 'build_id': os.environ.get('CNB_BUILD_ID'),
        'linux_commit': LOCK['linux']['commit'], 'components_commit': LOCK['components']['commit'],
        'config_sha256': sha256(WORK / 'build/.config'),
        'validation': 'Build and package validation only; board boot not tested by CI',
    }, indent=2) + '\n')
    (out / 'SHA256SUMS').write_text(''.join(sha256(path) + '  ' + path.name + '\n'
                                          for path in sorted(out.iterdir()) if path.is_file()))
    print('Kernel deb, corresponding sources and checksums ready in dist/kernel/')


if __name__ == '__main__':
    main()
