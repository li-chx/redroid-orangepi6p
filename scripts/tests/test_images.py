#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check pinned base-image identity across Docker storage backends."""
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import common


class ImageTests(unittest.TestCase):
    def inspect_base(self, info):
        with patch.object(common.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
                patch.object(common, 'image_info', return_value=info):
            return common.base_image(common.LOCK['base_image'])

    def test_classic_and_containerd_identities(self):
        for identity in [common.LOCK['base_image_id'], common.LOCK['base_image'].rsplit('@', 1)[1]]:
            with self.subTest(identity=identity):
                info = {'Id': identity, 'Architecture': 'arm64', 'Config': {}}
                self.assertEqual(self.inspect_base(info), info)

    def test_foreign_image_platform_and_volumes_are_rejected(self):
        base = {'Id': common.LOCK['base_image_id'], 'Architecture': 'arm64', 'Config': {}}
        for update in [{'Id': 'sha256:' + '0' * 64}, {'Architecture': 'amd64'},
                       {'Config': {'Volumes': {'/data': {}}}}]:
            with self.subTest(update=update), self.assertRaises(RuntimeError):
                self.inspect_base(dict(base, **update))


if __name__ == '__main__':
    unittest.main()
