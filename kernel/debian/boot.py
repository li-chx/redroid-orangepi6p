#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Manage the factory Orange Pi 6 Plus EFI GRUB entry; never reboot the board."""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import tempfile

RELEASE = '6.6.89-cix-redroid'
ENTRY_ID = 'orangepi6p-redroid'
BEGIN = '# BEGIN ORANGEPI6P-REDROID\n'
END = '# END ORANGEPI6P-REDROID\n'
ESP_TYPE = 'c12a7328-f81f-11d2-ba4b-00a0c93ec93b'


def run(*args):
    return subprocess.check_output([str(arg) for arg in args], text=True).strip()


def without_managed(text):
    if BEGIN not in text and END not in text:
        return text
    if text.count(BEGIN) != 1 or text.count(END) != 1 or text.index(END) < text.index(BEGIN):
        raise RuntimeError('Malformed managed GRUB section; refusing to edit')
    before, after = text.split(BEGIN)
    _, after = after.split(END)
    return before + after


def render_grub(text, root_partuuid, make_default=True):
    base = without_managed(text)
    blocks = re.findall(r'^menuentry\s+([^\n]+)\{\s*\n(.*?)^\}', base, flags=re.M | re.S)
    candidates = []
    for title, body in blocks:
        if 'orangepi6plus' not in re.sub(r'[^a-z0-9]', '', title.lower()):
            continue
        lines = body.replace('\\\n', ' ').splitlines()
        commands = [shlex.split(line) for line in lines if line.strip() and not line.lstrip().startswith('#')]
        linux = [cmd for cmd in commands if cmd and cmd[0] == 'linux' and len(cmd) > 2]
        if len(linux) == 1 and linux[0][1] == '/Image' and 'acpi=force' in linux[0][2:]:
            # Only the known factory no-initrd/ACPI boot layout is supported.
            if any(cmd[0] != 'linux' for cmd in commands):
                raise RuntimeError('Unsupported commands in factory ACPI entry')
            candidates.append(linux[0][2:])
    if len(candidates) != 1:
        raise RuntimeError('Expected one factory Orange Pi 6 Plus ACPI /Image entry')
    args = candidates[0]
    if [arg for arg in args if arg.startswith('root=')] != ['root=PARTUUID=' + root_partuuid]:
        raise RuntimeError('Factory GRUB root does not match this running root partition')
    if any(not re.fullmatch(r'[a-zA-Z0-9_=/.:,@+%\-]+', arg) for arg in args):
        raise RuntimeError('Unsupported shell syntax in factory kernel arguments')
    blocked = [arg.split('=', 1)[1] for arg in args if arg.startswith('module_blacklist=')]
    blacklist = list(dict.fromkeys([name for item in blocked for name in item.split(',')] + ['panthor']))
    args = [arg for arg in args if not arg.startswith('module_blacklist=')]
    args.append('module_blacklist=' + ','.join(blacklist))
    block = (BEGIN + f"menuentry 'Orange Pi 6 Plus ReDroid ({RELEASE})' --id '{ENTRY_ID}' {{\n"
             + '    linux /Image-redroid ' + ' '.join(args) + '\n}\n')
    if make_default:
        block += f"set default='{ENTRY_ID}'\nset timeout=5\n"
    return base.rstrip() + '\n\n' + block + END


def atomic_write(path, data):
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.', dir=path.parent)
    try:
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def register(esp, image, state, root_partuuid, make_default=True):
    config = esp / 'grub/grub.cfg'
    if not (esp / 'EFI/BOOT/BOOTAA64.EFI').is_file():
        raise RuntimeError('Factory ARM64 EFI loader is missing on the selected ESP')
    original = config.read_bytes()
    candidate = render_grub(original.decode(), root_partuuid, make_default).encode()
    content = image.read_bytes()
    if content[56:60] != b'ARM\x64':
        raise RuntimeError('Package Image does not have the ARM64 kernel magic')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Validate before publishing any ESP changes, then retain the factory recovery files.
    proposal = state / 'grub.cfg.proposed'
    atomic_write(proposal, candidate)
    run('grub-script-check', proposal)
    backup = state / 'grub.cfg.before-redroid'
    if not backup.exists():
        atomic_write(backup, original)
    atomic_write(state / 'grub.cfg.last-install', original)
    target = esp / 'Image-redroid'
    previous = target.read_bytes() if target.exists() else None
    if previous is not None and not (state / 'Image-redroid.before-install').exists():
        atomic_write(state / 'Image-redroid.before-install', previous)
    try:
        atomic_write(target, content)
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(content).digest():
            raise RuntimeError('ESP image read-back hash mismatch')
        atomic_write(config, candidate)
        if config.read_bytes() != candidate:
            raise RuntimeError('ESP GRUB read-back mismatch')
        atomic_write(state / 'installed.json', json.dumps({
            'release': RELEASE, 'entry_id': ENTRY_ID, 'make_default': make_default,
            'root_partuuid': root_partuuid, 'image_sha256': hashlib.sha256(content).hexdigest(),
        }, indent=2).encode() + b'\n')
    except BaseException:
        atomic_write(config, original)
        if previous is None:
            target.unlink(missing_ok=True)
        else:
            atomic_write(target, previous)
        raise
    os.sync()


def unregister(esp, state):
    if platform.release() == RELEASE:
        raise RuntimeError('Boot another kernel before removing the running ReDroid kernel')
    config = esp / 'grub/grub.cfg'
    original = config.read_text()
    updated = without_managed(original)
    if updated == original:
        return
    atomic_write(state / 'grub.cfg.last-remove', original.encode())
    proposal = state / 'grub.cfg.proposed'
    atomic_write(proposal, updated.encode())
    run('grub-script-check', proposal)
    atomic_write(config, updated.encode())
    # Leave Image-redroid and backups available for manual recovery. Only our menu is removed.
    os.sync()


def detect_esp(devices, root_source, configured=None):
    def flatten(entries):
        for entry in entries:
            yield entry
            yield from flatten(entry.get('children', []))
    entries = list(flatten(devices['blockdevices']))
    roots = [entry for entry in entries if Path(entry['name']).resolve() == Path(root_source).resolve()]
    if len(roots) != 1 or roots[0]['type'] != 'part' or not roots[0].get('partuuid'):
        raise RuntimeError('Only a directly partitioned root disk with PARTUUID is supported')
    root = roots[0]
    candidates = [entry for entry in entries if entry.get('pkname') == root.get('pkname')
                  and entry.get('pkname') and (entry.get('parttype') or '').lower() == ESP_TYPE
                  and entry.get('fstype') == 'vfat']
    if configured:
        candidates = [entry for entry in candidates if Path(entry['name']).resolve() == Path(configured).resolve()]
    if len(candidates) != 1:
        raise RuntimeError('Cannot select one FAT EFI partition on the root disk; configure esp_device')
    return candidates[0], root['partuuid']


@contextmanager
def mounted_esp(device):
    mounts = [Path(value) for value in device.get('mountpoints', []) if value]
    owned = not mounts
    target = mounts[0] if mounts else Path('/run/orangepi6p-redroid-kernel/esp')
    if owned:
        target.mkdir(parents=True, exist_ok=True, mode=0o700)
        run('mount', '-t', 'vfat', '-o', 'rw,nosuid,nodev,noexec', device['name'], target)
    try:
        actual = json.loads(run('findmnt', '--json', '--target', target, '--output', 'TARGET,SOURCE,FSTYPE,OPTIONS'))['filesystems'][0]
        if (actual['target'] != str(target) or actual['fstype'] != 'vfat'
                or Path(actual['source']).resolve() != Path(device['name']).resolve()
                or 'rw' not in actual['options'].split(',')):
            raise RuntimeError('Selected ESP is not mounted read-write at the expected target')
        yield target
    finally:
        if owned:
            run('umount', target)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install', 'remove'])
    args = parser.parse_args()
    state = Path('/var/lib/orangepi6p-redroid-kernel')
    # A failed first installation on an unsupported host must remain removable.
    if args.action == 'remove' and not (state / 'installed.json').exists():
        if platform.release() == RELEASE:
            raise RuntimeError('Boot another kernel before removing the running ReDroid kernel')
        print('No managed boot entry was installed')
        return
    if os.geteuid() != 0 or platform.machine() != 'aarch64' or not Path('/sys/firmware/efi').is_dir():
        raise RuntimeError('Run on the Debian ARM64 board booted through EFI as root')
    if not re.search(r'^ID=(?:"debian"|debian)$', Path('/etc/os-release').read_text(), re.M):
        raise RuntimeError('Only the factory Debian layout is supported')
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    config = Path('/etc/orangepi6p-redroid-kernel.json')
    options = json.loads(config.read_text())
    if not isinstance(options.get('make_default'), bool):
        raise RuntimeError('make_default must be a JSON boolean')
    with (state / 'boot.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        devices = json.loads(run('lsblk', '--json', '--paths', '--output', 'NAME,TYPE,PARTTYPE,FSTYPE,PARTUUID,PKNAME,MOUNTPOINTS'))
        root_source = run('findmnt', '--noheadings', '--output', 'SOURCE', '--target', '/')
        device, root_partuuid = detect_esp(devices, root_source, options.get('esp_device'))
        with mounted_esp(device) as esp:
            if args.action == 'install':
                register(esp, Path('/boot/vmlinuz-' + RELEASE), state, root_partuuid, options['make_default'])
            else:
                unregister(esp, state)
    print(f'ReDroid boot entry {args.action} complete; no reboot was performed')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        raise SystemExit('ReDroid boot registration failed: ' + str(error)) from None
