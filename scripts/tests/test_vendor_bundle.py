#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check vendor imports and rejected downloads without network or factory files."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


vendor = load('vendor_bundle', SCRIPTS / 'import-vendor-bundle.py')
download = load('vendor_download', SCRIPTS / 'download-vendor.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


class VendorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=vendor.WORK / 'tmp')
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        (self.work / 'tmp').mkdir()
        self.files = {'vendor/bin/service': b'service', 'vendor/lib64/driver.so': b'driver'}
        self.lock = {'vendor_files': [{'source': name, 'sha256': sha(data)}
                                     for name, data in self.files.items()]}
        self.settings = {'sha256': '', 'root_directory': 'bundle'}
        self.archive = self.work / 'bundle.tar.gz'
        for name, value in [('WORK', self.work), ('LOCK', self.lock), ('BUNDLE', self.settings)]:
            context = patch.object(vendor, name, value)
            context.start()
            self.addCleanup(context.stop)

    def bundle(self, additions=(), omit=None, mutate=None, catalog=None):
        files = dict(self.files)
        if mutate:
            files.update(mutate)
        files.update({'inputs.lock.json': json.dumps(catalog or self.lock).encode(),
                      'PROVENANCE.json': b'{}', 'README.md': b'fixture', 'NOTICE': b'original notice'})
        files['SHA256SUMS'] = ''.join(sha(data) + '  ' + name + '\n'
                                     for name, data in sorted(files.items())).encode()
        with tarfile.open(self.archive, 'w:gz') as archive:
            for name, data in files.items():
                if name == omit:
                    continue
                info = tarfile.TarInfo('bundle/' + name)
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            for info in additions:
                archive.addfile(info, io.BytesIO(b'x') if info.isfile() else None)
        self.settings['sha256'] = sha(self.archive.read_bytes())

    def test_import_and_cache_reuse(self):
        self.bundle()
        result = vendor.import_bundle(self.archive)
        self.assertEqual((result / 'lib64/driver.so').read_bytes(), b'driver')
        self.assertTrue((result / 'bin/service').stat().st_mode & 0o111)
        self.assertEqual(vendor.import_bundle(self.archive), result)
        (result / 'lib64/driver.so').write_bytes(b'corrupt cache')
        with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
            vendor.import_bundle(self.archive)

    def test_archive_hash_is_checked_before_import(self):
        self.bundle()
        self.archive.write_bytes(b'corrupt archive')
        with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
            vendor.import_bundle(self.archive)
        self.assertFalse((self.work / 'vendor-input').exists())

    def test_rejects_traversal_links_duplicate_and_extra_files(self):
        for name, kind in [('bundle/../escape', tarfile.REGTYPE),
                           ('/outside', tarfile.REGTYPE),
                           ('bundle/vendor/bin/service', tarfile.SYMTYPE),
                           ('bundle/vendor/bin/service', tarfile.REGTYPE),
                           ('bundle/extra', tarfile.REGTYPE)]:
            with self.subTest(name=name, kind=kind):
                info = tarfile.TarInfo(name)
                info.type = kind
                info.size = 1 if kind == tarfile.REGTYPE else 0
                info.linkname = '/outside' if kind == tarfile.SYMTYPE else ''
                self.bundle(additions=[info])
                with self.assertRaises(RuntimeError):
                    vendor.import_bundle(self.archive)
                self.assertFalse((self.work / 'vendor-input').exists())
                self.assertEqual(list((self.work / 'tmp').iterdir()), [])

    def test_missing_file_and_modified_vendor_are_rejected(self):
        self.bundle(omit='vendor/lib64/driver.so')
        with self.assertRaisesRegex(RuntimeError, 'missing required files'):
            vendor.import_bundle(self.archive)
        self.bundle(mutate={'vendor/lib64/driver.so': b'changed but internally checksummed'})
        with self.assertRaisesRegex(RuntimeError, 'SHA256 mismatch'):
            vendor.import_bundle(self.archive)
        self.assertFalse((self.work / 'vendor-input').exists())

    def test_different_catalog_is_rejected(self):
        self.bundle(catalog={'vendor_files': []})
        with self.assertRaisesRegex(RuntimeError, 'catalog differs'):
            vendor.import_bundle(self.archive)

    def test_download_hash_and_size_limits(self):
        destination = self.work / 'download.tar.gz'
        opener = unittest.mock.Mock()
        with patch.object(download.urllib.request, 'build_opener', return_value=opener):
            opener.open.side_effect = lambda *args, **kwargs: io.BytesIO(b'payload')
            with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
                download.download('https://example.invalid/file', destination, '0' * 64)
            with self.assertRaisesRegex(ValueError, 'exceeds the limit'):
                download.download('https://example.invalid/file', destination, sha(b'payload'), maximum=1)
            self.assertFalse(destination.exists())
            self.assertFalse(destination.with_suffix('.gz.partial').exists())
            download.download('https://example.invalid/file', destination, sha(b'payload'))
            self.assertEqual(destination.read_bytes(), b'payload')

    def test_plain_http_and_url_credentials_are_rejected(self):
        for url in ['http://example.invalid/file', 'https://name:secret@example.invalid/file']:
            with self.assertRaises(ValueError):
                download.download(url, self.work / 'download', '0' * 64)
        with self.assertRaisesRegex(ValueError, 'Only HTTPS redirects'):
            download.HTTPSRedirects().redirect_request(None, None, 302, '', {}, 'http://example.invalid/file')


if __name__ == '__main__':
    unittest.main()
