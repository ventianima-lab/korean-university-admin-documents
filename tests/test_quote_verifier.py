"""Synthetic caption/structure tests; these do not validate real screenshots."""
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/hwpx-internet-comparison-quotes/scripts/verify_quote_hwpx.py'
HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'


class QuoteVerifierTests(unittest.TestCase):
    def run_case(self, quantity=2, price=220, inline='1', comparison_first=False):
        root = ET.Element('section')
        captions = ['품목 | 가상 모델 A | 수량 2개 | 총액 200원 | 출처 가상 판매처 A',
                    f'비교견적 1 | 품목 | 가상 모델 A | 수량 {quantity}개 | 총액 {price}원 | 출처 가상 판매처 B']
        if comparison_first:
            captions.reverse()
        for caption in captions:
            paragraph = ET.SubElement(root, f'{{{HP}}}p')
            ET.SubElement(paragraph, f'{{{HP}}}t').text = caption
            picture = ET.SubElement(paragraph, f'{{{HP}}}pic')
            ET.SubElement(picture, f'{{{HP}}}pos', treatAsChar=inline, flowWithText='1')
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'synthetic.hwpx'
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('mimetype', 'application/hwp+zip')
                archive.writestr('Contents/section0.xml', ET.tostring(root))
            return subprocess.run([sys.executable, str(SCRIPT), str(path), '--expected-main', '1',
                                   '--comparisons-per-main', '1'], capture_output=True).returncode

    def test_matching_captions_pass(self):
        self.assertEqual(self.run_case(), 0)

    def test_wrong_quantity_fails(self):
        self.assertEqual(self.run_case(quantity=3), 1)

    def test_nonhigher_price_fails(self):
        self.assertEqual(self.run_case(price=200), 1)

    def test_floating_image_fails(self):
        self.assertEqual(self.run_case(inline='0'), 1)

    def test_comparison_before_main_fails(self):
        self.assertEqual(self.run_case(comparison_first=True), 1)


if __name__ == '__main__':
    unittest.main()
