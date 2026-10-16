#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify header content pins survive repacking and reject changed source."""
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
spec = importlib.util.spec_from_file_location('fetch_headers', SCRIPTS / 'fetch-headers.py')
headers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(headers)


class HeaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=headers.WORK / 'tmp')
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        hashes = {'test.h': hashlib.sha256(b'pinned header').hexdigest()}
        self.item = {'file': 'fixture.tar.gz', 'regular_files': 1,
                     'tree_sha256': hashlib.sha256(json.dumps(hashes, sort_keys=True,
                                                             separators=(',', ':')).encode()).hexdigest()}

    def archive(self, name='test.h', content=b'pinned header', mtime=0, duplicate=False, link=False):
        path = self.work / 'fixture.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for _ in range(2 if duplicate else 1):
                member = tarfile.TarInfo(name)
                member.size = len(content)
                member.mtime = mtime
                member.uid = mtime
                archive.addfile(member, io.BytesIO(content))
            if link:
                member = tarfile.TarInfo('outside-link')
                member.type = tarfile.SYMTYPE
                member.linkname = '../../outside'
                archive.addfile(member)
        return path

    def test_repacking_preserves_source_identity(self):
        first = self.archive().read_bytes()
        self.assertEqual(headers.header_files(self.work / 'fixture.tar.gz', self.item), {'test.h': b'pinned header'})
        second = self.archive(mtime=12345, link=True)
        self.assertNotEqual(first, second.read_bytes())
        self.assertEqual(headers.header_files(second, self.item), {'test.h': b'pinned header'})

    def test_modified_contents_paths_and_duplicates_fail(self):
        for options in [{'content': b'changed'}, {'name': 'other.h'}, {'name': '../escape'},
                        {'name': '/absolute'}, {'duplicate': True}]:
            with self.subTest(options=options), self.assertRaises(RuntimeError):
                headers.header_files(self.archive(**options), self.item)

    def test_bad_download_is_not_cached_and_existing_partial_is_preserved(self):
        item = {'file': 'single.h', 'url': 'https://example.invalid/header',
                'sha256': hashlib.sha256(b'header').hexdigest()}
        with patch.object(headers, 'WORK', self.work):
            with patch.object(headers.urllib.request, 'urlopen', return_value=io.BytesIO(b'wrong')):
                with self.assertRaises(RuntimeError):
                    headers.fetch(item)
            cache = self.work / 'cache/single.h'
            partial = cache.with_suffix('.h.partial')
            self.assertFalse(cache.exists())
            self.assertFalse(partial.exists())
            partial.write_bytes(b'old partial')
            with self.assertRaisesRegex(RuntimeError, 'partial header'):
                headers.fetch(item)
            self.assertEqual(partial.read_bytes(), b'old partial')


if __name__ == '__main__':
    unittest.main()
