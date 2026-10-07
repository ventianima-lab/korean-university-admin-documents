#!/usr/bin/env python3
"""Behavior checks for preserving a user-edited final during a narrow follow-up."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
import verify_hwpx_followup as check


class FollowupChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.before = self.root/'baseline.hwpx'
        self.after = self.root/'candidate.hwpx'
        self.package(self.before, ['user-revised code', 'old report A', 'old report B', 'paid amount'])
        self.package(self.after, ['user-revised code', 'continuous longer report', 'paid amount'])
        self.omit_before = {'Contents/section0.xml':{1, 2}}
        self.omit_after = {'Contents/section0.xml':{1}}

    def package(self, path, texts, font='7', picture=b'original media'):
        content = '<hs:sec xmlns:hs="urn:section" xmlns:hp="'+check.HP+'">'
        for i, text in enumerate(texts):
            content += '<hp:p id="'+str(i)+'"><hp:run charPrIDRef="'+font+'"><hp:t>'+text+'</hp:t></hp:run></hp:p>'
        content += '</hs:sec>'
        with ZipFile(path, 'w') as z:
            z.writestr('Contents/section0.xml', content)
            z.writestr('Contents/header.xml', '<header><style font="source font"/></header>')
            z.writestr('BinData/image1.png', picture)

    def run_check(self):
        return check.verify(self.before, self.after, self.omit_before, self.omit_after)

    def test_continuous_report_preserves_current_user_values(self):
        self.assertEqual(self.run_check()['preserved_blocks'], 2)

    def test_rebuilding_from_stale_draft_is_rejected(self):
        self.package(self.after, ['earlier code', 'continuous longer report', 'paid amount'])
        with self.assertRaises(ValueError): self.run_check()

    def test_unrequested_font_change_is_rejected(self):
        self.package(self.after, ['user-revised code', 'continuous longer report', 'paid amount'], font='8')
        with self.assertRaises(ValueError): self.run_check()

    def test_original_media_loss_is_rejected(self):
        self.package(self.after, ['user-revised code', 'continuous longer report', 'paid amount'], picture=b'replaced media')
        with self.assertRaises(ValueError): self.run_check()

    def test_invalid_scope_is_rejected(self):
        self.omit_after['Contents/section0.xml'].add(9)
        with self.assertRaises(ValueError): self.run_check()

    def test_live_edit_during_run_blocks_replacement(self):
        live = self.root/'live.hwpx'
        live.write_bytes(self.before.read_bytes())
        expected = check.sha256(live)
        self.package(live, ['new user edit', 'old report A', 'old report B', 'paid amount'])
        result = subprocess.run([sys.executable, str(Path(check.__file__)), str(self.before), str(self.after),
                                 '--baseline-exclude', 'Contents/section0.xml:1,2',
                                 '--candidate-exclude', 'Contents/section0.xml:1',
                                 '--live-path', str(live), '--expected-live-sha256', expected],
                                capture_output=True, text=True,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.assertEqual(result.returncode, 1)
        self.assertIn('Live working final changed', result.stdout)


if __name__ == '__main__':
    unittest.main()
