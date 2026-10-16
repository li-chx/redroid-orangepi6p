# SPDX-License-Identifier: MIT
"""Isolated input-fetch, boot-registration and deb-archive checks; never install a package."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

KERNEL = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


boot = load('boot', KERNEL / 'debian/boot.py')
package = load('kernel_package', KERNEL / 'package.py')
fetch = load('kernel_fetch', KERNEL / 'fetch-sources.py')
ROOT_UUID = '11111111-2222-3333-4444-555555555555'
FACTORY = f'''set default=0
set timeout=5
menuentry '0 OrangePi 6 Plus (ACPI)' {{
    linux /Image \\
        console=ttyAMA2,115200 acpi=force \\
        root=PARTUUID={ROOT_UUID} rootwait rw
}}
menuentry '1 OrangePi 6 Plus (Device Tree)' {{
    devicetree /sky1-orangepi-6-plus.dtb
    linux /Image acpi=off root=PARTUUID={ROOT_UUID} rootwait rw
}}
'''


class FetchTests(unittest.TestCase):
    def source_fixture(self, root):
        upstream = root / 'upstream'
        upstream.mkdir()
        for name in ['selected/input.txt', 'unrelated/other.txt']:
            path = upstream / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(name + '\n')
        fetch.run('git', '-C', upstream, 'init', '--quiet')
        fetch.run('git', '-C', upstream, 'add', '.')
        fetch.run('git', '-C', upstream, '-c', 'user.name=Fixture',
                  '-c', 'user.email=fixture@example.invalid', 'commit', '--no-gpg-sign',
                  '--quiet', '-m', 'fixture')
        revision = fetch.run('git', '-C', upstream, 'rev-parse', 'HEAD',
                             capture_output=True, text=True).stdout.strip()
        return {'url': upstream.as_uri(), 'commit': revision, 'submodule': 'upstream'}

    def test_prepared_source_accepts_git_directory_and_submodule_pointer_without_fetch(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            spec = self.source_fixture(root)
            target = root / spec['submodule']
            with patch.object(fetch, 'KERNEL', root), patch.object(fetch, 'run', wraps=fetch.run) as run:
                self.assertEqual(fetch.source('linux', spec), target)
                self.assertTrue(all(call.args[3] == 'rev-parse' for call in run.call_args_list))
            fetch.run('git', '-C', root, 'init', '--quiet')
            fetch.run('git', '-C', root, 'submodule', 'add', spec['url'], spec['submodule'])
            fetch.run('git', '-C', root, 'submodule', 'absorbgitdirs')
            self.assertTrue((target / '.git').is_file())
            (target / 'selected/input.txt').write_text('build patch\n')
            with patch.object(fetch, 'KERNEL', root), patch.object(fetch, 'run', wraps=fetch.run) as run:
                self.assertEqual(fetch.source('linux', spec), target)
                self.assertTrue(all(call.args[3] == 'rev-parse' for call in run.call_args_list))
            self.assertEqual((target / 'selected/input.txt').read_text(), 'build patch\n')

    def test_uninitialized_source_does_not_fall_back_to_parent_repository(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            spec = self.source_fixture(root)
            with patch.object(fetch, 'KERNEL', root):
                with self.assertRaisesRegex(RuntimeError, 'Missing kernel submodule'):
                    fetch.source('linux', dict(spec, submodule='missing'))
                fetch.run('git', '-C', root, 'init', '--quiet')
                (root / 'empty').mkdir()
                with self.assertRaisesRegex(RuntimeError, 'Missing kernel submodule'):
                    fetch.source('linux', dict(spec, submodule='empty'))

    def test_wrong_commit_and_missing_selected_directory_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            spec = self.source_fixture(root)
            with patch.object(fetch, 'KERNEL', root):
                with self.assertRaisesRegex(RuntimeError, 'Source commit mismatch'):
                    fetch.source('linux', dict(spec, commit='0' * 40))
                with self.assertRaisesRegex(RuntimeError, 'Missing selected source directory'):
                    fetch.source('components', dict(spec, paths=['missing']))
                self.assertEqual(fetch.source('components', dict(spec, paths=['selected'])), root / 'upstream')

    def test_unrelated_component_binary_changes_do_not_block_selected_driver_sources(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            spec = dict(self.source_fixture(root), paths=['selected'])
            target = root / spec['submodule']
            # Reproduce a full checkout whose unused binary differs from the Git blob.
            (target / 'unrelated/other.txt').write_bytes(b'\x00unused materialized binary\xff')
            whole_tree = subprocess.run(['git', '-C', str(target), 'diff', '--exit-code', 'HEAD'],
                                        capture_output=True)
            self.assertEqual(whole_tree.returncode, 1)
            with patch.object(fetch, 'KERNEL', root):
                self.assertEqual(fetch.source('components', spec), target)
            self.assertEqual((target / 'unrelated/other.txt').read_bytes(),
                             b'\x00unused materialized binary\xff')

    def test_selected_component_changes_are_rejected_in_worktree_and_index(self):
        for staged in [False, True]:
            with self.subTest(staged=staged), \
                    tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
                root = Path(directory)
                spec = dict(self.source_fixture(root), paths=['selected'])
                target = root / spec['submodule']
                (target / 'selected/input.txt').write_text('changed driver source\n')
                if staged:
                    fetch.run('git', '-C', target, 'add', 'selected/input.txt')
                with patch.object(fetch, 'KERNEL', root):
                    with self.assertRaises(subprocess.CalledProcessError):
                        fetch.source('components', spec)

    def test_fresh_workspace_initializes_both_pinned_submodules(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            project = root / 'project'
            project.mkdir()
            fetch.run('git', '-C', project, 'init', '--quiet')
            specs = {}
            for name in ['linux', 'components']:
                remote = root / (name + '-remote')
                remote.mkdir()
                specs[name] = dict(self.source_fixture(remote), submodule='upstream/' + name)
                fetch.run('git', '-C', project, '-c', 'protocol.file.allow=always', 'submodule',
                          'add', '--quiet', specs[name]['url'], specs[name]['submodule'])
            fetch.run('git', '-C', project, '-c', 'user.name=Fixture', '-c',
                      'user.email=fixture@example.invalid', 'commit', '--no-gpg-sign', '--quiet', '-m', 'pins')
            workspace = root / 'workspace'
            fetch.run('git', 'clone', '--quiet', project, workspace)
            with patch.object(fetch, 'KERNEL', workspace):
                with self.assertRaisesRegex(RuntimeError, 'Missing kernel submodule'):
                    fetch.source('linux', specs['linux'])
                fetch.run('git', '-C', workspace, '-c', 'protocol.file.allow=always', 'submodule',
                          'update', '--init', '--recursive', '--force')
                for name, spec in specs.items():
                    target = fetch.source(name, dict(spec, paths=['selected']))
                    self.assertTrue((target / '.git').is_file())
                    self.assertTrue((target / 'selected/input.txt').is_file())

    def toolchain_fixture(self, root):
        work = root / 'work'
        archive = work / 'downloads/fixture.tar.xz'
        archive.parent.mkdir(parents=True)
        source = root / 'fixture/bin'
        source.mkdir(parents=True)
        compiler = source / 'test-gcc'
        compiler.write_text('#!/bin/sh\nprintf "fixture compiler\\n"\n')
        compiler.chmod(0o755)
        (source / 'compiler-link').symlink_to('test-gcc')
        with tarfile.open(archive, 'w:xz') as stream:
            stream.add(source.parent, arcname='fixture')
        spec = {'directory': 'fixture', 'prefix': 'test-', 'sha256': fetch.sha256(archive)}
        return work, archive, spec

    def test_toolchain_extracts_without_python_filter_api(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            work, archive, spec = self.toolchain_fixture(Path(directory))
            with patch.object(fetch, 'WORK', work), patch.object(fetch, 'LOCK', {'toolchain': spec}), \
                    patch.object(tarfile.TarFile, 'extractall', side_effect=TypeError('filter unsupported')):
                fetch.toolchain()
                fetch.toolchain()  # Reuse a complete toolchain.
            binary = work / 'toolchains/fixture/bin'
            self.assertTrue(os.access(binary / 'test-gcc', os.X_OK))
            self.assertTrue((binary / 'compiler-link').is_symlink())
            self.assertEqual((binary / 'compiler-link').read_bytes(), (binary / 'test-gcc').read_bytes())
            self.assertFalse(list((work / 'toolchains').glob('.extract-*')))

    def test_toolchain_hash_mismatch_prevents_extraction(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            work, archive, spec = self.toolchain_fixture(Path(directory))
            archive.write_bytes(b'corrupt download')
            with patch.object(fetch, 'WORK', work), patch.object(fetch, 'LOCK', {'toolchain': spec}):
                with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
                    fetch.toolchain()
            self.assertFalse((work / 'toolchains').exists())

    def test_failed_toolchain_extraction_does_not_publish_partial_directory(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            work, archive, spec = self.toolchain_fixture(Path(directory))
            def fail_extract(*args, **kwargs):
                extraction = Path(args[args.index('--directory') + 1]) / 'fixture'
                extraction.mkdir()
                (extraction / 'incomplete').touch()
                raise subprocess.CalledProcessError(2, ['tar'])
            with patch.object(fetch, 'WORK', work), patch.object(fetch, 'LOCK', {'toolchain': spec}), \
                    patch.object(fetch, 'run', side_effect=fail_extract):
                with self.assertRaises(subprocess.CalledProcessError):
                    fetch.toolchain()
            self.assertEqual(list((work / 'toolchains').iterdir()), [])

class BootTests(unittest.TestCase):
    def test_failed_initial_install_can_be_removed_on_unsupported_host(self):
        with patch.object(boot.platform, 'release', return_value='other-kernel'), \
                patch.object(boot.Path, 'exists', return_value=False), \
                patch.object(sys, 'argv', ['boot.py', 'remove']), \
                patch.object(boot, 'run') as external:
            boot.main()
            external.assert_not_called()

    @unittest.skipUnless(shutil.which('grub-script-check'), 'GRUB checker unavailable')
    def test_generated_entry_passes_real_grub_parser(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            candidate = Path(directory) / 'grub.cfg'
            candidate.write_text(boot.render_grub(FACTORY, ROOT_UUID))
            subprocess.run(['grub-script-check', str(candidate)], check=True)

    def test_entry_is_idempotent_and_keeps_factory(self):
        result = boot.render_grub(FACTORY, ROOT_UUID)
        self.assertTrue(result.startswith(FACTORY))
        self.assertIn("set default='orangepi6p-redroid'", result)
        self.assertIn('module_blacklist=panthor', result)
        self.assertNotIn('redroid2', result)
        self.assertEqual(boot.render_grub(result, ROOT_UUID), result)
        self.assertEqual(boot.without_managed(result).strip(), FACTORY.strip())

    def test_optional_default_and_existing_blacklist(self):
        original = FACTORY.replace('acpi=force', 'acpi=force module_blacklist=other,panthor')
        result = boot.render_grub(original, ROOT_UUID, False)
        self.assertNotIn("set default='orangepi6p-redroid'", result)
        self.assertEqual(result.count('module_blacklist=other,panthor'), 2)

    def test_rejects_wrong_disk_and_unsupported_templates(self):
        for text, uuid in [(FACTORY, 'wrong-disk'),
                           (FACTORY + FACTORY, ROOT_UUID),
                           (FACTORY.replace('acpi=force', 'acpi=off'), ROOT_UUID),
                           (FACTORY.replace('rootwait rw', 'rootwait rw\n    initrd /old-initrd'), ROOT_UUID),
                           (FACTORY + boot.BEGIN, ROOT_UUID)]:
            with self.subTest(text=text), self.assertRaises(RuntimeError):
                boot.render_grub(text, uuid)

    def test_register_and_remove_use_isolated_esp(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            esp = root / 'esp'
            (esp / 'grub').mkdir(parents=True)
            (esp / 'EFI/BOOT').mkdir(parents=True)
            (esp / 'EFI/BOOT/BOOTAA64.EFI').write_bytes(b'EFI fixture')
            (esp / 'grub/grub.cfg').write_text(FACTORY)
            (esp / 'Image').write_bytes(b'factory kernel')
            image = root / 'vmlinuz'
            image.write_bytes(bytes(56) + b'ARM\x64' + bytes(4))
            state = root / 'state'
            with patch.object(boot, 'run', return_value='') as check, patch.object(boot.os, 'sync'):
                boot.register(esp, image, state, ROOT_UUID)
                self.assertEqual((esp / 'Image-redroid').read_bytes(), image.read_bytes())
                self.assertEqual((esp / 'Image').read_bytes(), b'factory kernel')
                self.assertEqual((state / 'grub.cfg.before-redroid').read_text(), FACTORY)
                boot.register(esp, image, state, ROOT_UUID)
                self.assertEqual((esp / 'grub/grub.cfg').read_text().count(boot.BEGIN), 1)
                self.assertTrue(check.called)
                with patch.object(boot.platform, 'release', return_value=boot.RELEASE), self.assertRaises(RuntimeError):
                    boot.unregister(esp, state)
                with patch.object(boot.platform, 'release', return_value='factory'):
                    boot.unregister(esp, state)
                self.assertEqual((esp / 'grub/grub.cfg').read_text().strip(), FACTORY.strip())

    def test_failed_publish_restores_old_config_and_image(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            esp = root / 'esp'
            (esp / 'grub').mkdir(parents=True)
            (esp / 'EFI/BOOT').mkdir(parents=True)
            (esp / 'EFI/BOOT/BOOTAA64.EFI').write_bytes(b'EFI')
            (esp / 'grub/grub.cfg').write_text(FACTORY)
            (esp / 'Image-redroid').write_bytes(b'previous test kernel')
            image = root / 'vmlinuz'
            image.write_bytes(bytes(56) + b'ARM\x64' + bytes(4))
            write = boot.atomic_write
            failed = False
            def fail_once(path, data):
                nonlocal failed
                if path == esp / 'grub/grub.cfg' and not failed:
                    failed = True
                    raise OSError('simulated full ESP')
                write(path, data)
            with patch.object(boot, 'run', return_value=''), patch.object(boot, 'atomic_write', side_effect=fail_once):
                with self.assertRaises(OSError):
                    boot.register(esp, image, root / 'state', ROOT_UUID)
            self.assertEqual((esp / 'grub/grub.cfg').read_text(), FACTORY)
            self.assertEqual((esp / 'Image-redroid').read_bytes(), b'previous test kernel')

    def test_esp_must_be_unique_and_on_root_disk(self):
        root = {'name': '/dev/testdisk2', 'type': 'part', 'partuuid': ROOT_UUID, 'pkname': '/dev/testdisk'}
        esp = {'name': '/dev/testdisk1', 'type': 'part', 'pkname': '/dev/testdisk',
               'parttype': boot.ESP_TYPE, 'fstype': 'vfat', 'mountpoints': [None]}
        devices = {'blockdevices': [root, esp]}
        self.assertEqual(boot.detect_esp(devices, root['name']), (esp, ROOT_UUID))
        duplicate = {**esp, 'name': '/dev/testdisk3'}
        with self.assertRaises(RuntimeError):
            boot.detect_esp({'blockdevices': [root, esp, duplicate]}, root['name'])
        with self.assertRaises(RuntimeError):
            boot.detect_esp({'blockdevices': [root, {**esp, 'pkname': '/dev/other'}]}, root['name'])


class PackageTests(unittest.TestCase):
    def test_corresponding_source_archive_excludes_unselected_trees_git_and_owner_metadata(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            work = Path(directory)
            linux = work / 'linux'
            linux.mkdir()
            (linux / '.git').write_text('gitdir: private pointer')
            (linux / 'nested/.git').mkdir(parents=True)
            (linux / 'nested/.git/config').write_text('must not be distributed')
            (linux / 'example.c').write_text('/* source fixture */\n')
            components = work / 'components'
            for name in package.LOCK['components']['paths']:
                selected = components / name
                selected.mkdir(parents=True)
                (selected / 'driver.c').write_text('/* selected driver */\n')
            for name in ['cix_proprietary/private.c', 'cix_opensource/unrelated/private.c']:
                unselected = components / name
                unselected.parent.mkdir(parents=True, exist_ok=True)
                unselected.write_text('must not be distributed')
            (work / 'build').mkdir()
            (work / 'build/.config').write_text('CONFIG_ARM64=y\n')
            target = work / 'source.tar.xz'
            lock = dict(package.LOCK, linux={'submodule': str(linux)},
                        components=dict(package.LOCK['components'], submodule=str(components)))
            with patch.object(package, 'WORK', work), patch.object(package, 'LOCK', lock), \
                    patch.dict(os.environ, {'SOURCE_DATE_EPOCH': '123'}):
                package.source_archive(target)
            with tarfile.open(target) as archive:
                members = archive.getmembers()
                self.assertFalse(any('.git' in Path(member.name).parts for member in members))
                self.assertFalse(any('private.c' in member.name for member in members))
                for name in lock['components']['paths']:
                    self.assertEqual(archive.extractfile('sources/' + name + '/driver.c').read(),
                                     b'/* selected driver */\n')
                self.assertTrue(all(member.uid == 0 and member.gid == 0 and member.uname == ''
                                    and member.gname == '' and member.mtime == 123 for member in members))
                self.assertEqual(archive.extractfile('build/config.final').read(), b'CONFIG_ARM64=y\n')

    def test_project_export_prunes_populated_submodules_and_work_before_reading_files(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            root = Path(directory)
            for name in ['src', 'scripts', 'config', 'docs', 'kernel', 'LICENSES', '.ci', '.cnb']:
                (root / name).mkdir()
            for name in ['README.md', 'LICENSE', 'NOTICE', 'Dockerfile', '.dockerignore', '.gitignore',
                         '.gitattributes', '.gitmodules', '.cnb.yml']:
                (root / name).write_text('fixture\n')
            project = KERNEL.parent
            for name in ['export-source.py', 'common.py']:
                shutil.copyfile(project / 'scripts' / name, root / 'scripts' / name)
            (root / 'config/inputs.lock.json').write_text('{}')
            for name in ['kernel/upstream/linux/private.c', 'kernel/upstream/components/private.so',
                         'kernel/work/cache/private.key']:
                target = root / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text('-----BEGIN ' + 'RSA PRIVATE KEY-----')
            subprocess.run([sys.executable, str(root / 'scripts/export-source.py')], check=True)
            with tarfile.open(root / 'dist/orangepi6p-redroid-source.tar.gz') as archive:
                names = archive.getnames()
                self.assertIn('orangepi6p-redroid/.gitmodules', names)
                self.assertFalse(any('/kernel/upstream/' in name or '/kernel/work/' in name for name in names))

    def stage(self, directory):
        stage = Path(directory) / 'stage'
        (stage / 'boot').mkdir(parents=True)
        (stage / ('boot/vmlinuz-' + package.RELEASE)).write_bytes(bytes(56) + b'ARM\x64' + bytes(4))
        modules = stage / 'lib/modules' / package.RELEASE / 'extra'
        modules.mkdir(parents=True)
        header = b'\x7fELF\x02\x01' + bytes(12) + b'\xb7\x00'
        for name in package.VENDOR_MODULES:
            (modules / name).write_bytes(header)
        dtbs = stage / 'boot' / ('dtb-' + package.RELEASE) / 'cix'
        dtbs.mkdir(parents=True)
        for name in ['sky1-orangepi-6-plus', 'sky1-orangepi-6-plus-40pin', 'sky1-orangepi-6-plus-40pin-pwm']:
            (dtbs / (name + '.dtb')).write_bytes(b'dtb fixture')
        return stage

    def test_stage_rejects_wrong_architecture_and_missing_module(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            stage = self.stage(directory)
            with patch.object(package, 'output', return_value=package.RELEASE + ' SMP preempt mod_unload aarch64'):
                self.assertEqual(package.verify_stage(stage), 6)
                module = stage / 'lib/modules' / package.RELEASE / 'extra/amvx.ko'
                module.write_bytes(b'wrong architecture')
                with self.assertRaises(RuntimeError):
                    package.verify_stage(stage)
                module.unlink()
                with self.assertRaises(RuntimeError):
                    package.verify_stage(stage)

    def test_stage_rejects_foreign_vermagic(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            stage = self.stage(directory)
            with patch.object(package, 'output', return_value='6.6.89-cix-redroid2 SMP preempt'):
                with self.assertRaises(RuntimeError):
                    package.verify_stage(stage)

    def test_real_deb_contains_boot_integration_and_conffile(self):
        with tempfile.TemporaryDirectory(dir=KERNEL / 'work/tmp') as directory:
            stage = self.stage(directory)
            deb = Path(directory) / 'kernel.deb'
            package.build_deb(stage, deb, package.RELEASE + '-1+20261016')
            self.assertEqual(subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Architecture'], text=True).strip(), 'arm64')
            self.assertEqual(subprocess.check_output(['dpkg-deb', '-f', str(deb), 'Package'], text=True).strip(),
                             'linux-image-6.6.89-cix-redroid')
            control = Path(directory) / 'control'
            subprocess.run(['dpkg-deb', '--control', str(deb), str(control)], check=True)
            self.assertIn('/etc/orangepi6p-redroid-kernel.json', (control / 'conffiles').read_text())
            self.assertIn('boot.py install', (control / 'postinst').read_text())
            self.assertIn('boot.py remove', (control / 'prerm').read_text())
            self.assertTrue((control / 'postinst').stat().st_mode & 0o111)


if __name__ == '__main__':
    (KERNEL / 'work/tmp').mkdir(parents=True, exist_ok=True)
    unittest.main()
