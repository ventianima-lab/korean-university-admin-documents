from __future__ import annotations

import copy
import tempfile
import unittest
import zipfile
from pathlib import Path

from verify_quote_capture_review import CHECKS, HP, digest, review_issues
from verify_quote_hwpx import caption_source


class CaptureReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.doc = self.base / 'quote.hwpx'
        with zipfile.ZipFile(self.doc, 'w') as z:
            z.writestr('Contents/section0.xml', f'<s xmlns:hp="{HP}"><hp:pic id="42"/></s>')
        for name in ('original.png', 'render.png'):
            (self.base / name).write_bytes(name.encode())
        entry = dict.fromkeys(CHECKS, True)
        entry.update(picture_id='42', seller='Example Store', seller_identity='Example Merchant', source_kind='product_detail')
        for kind in ('original', 'render'):
            entry[kind + '_file'] = kind + '.png'
            entry[kind + '_sha256'] = digest(self.base / (kind + '.png'))
        self.manifest = {'document_sha256': digest(self.doc), 'captures': [entry]}

    def check(self, manifest=None):
        return review_issues(self.doc, manifest or self.manifest, self.base)

    def test_complete_review(self):
        self.assertEqual(self.check(), [])

    def test_caption_source_accepts_trailing_confirmation_date(self):
        self.assertEqual(caption_source('품목 예시 | 출처 Example Store | 확인일 2030-01-02'), 'Example Store')
        self.assertEqual(caption_source('품목 예시 | 출처 Example Store'), 'Example Store')
        self.assertEqual(caption_source('출처 First | 판매처 Second'), '')

    def test_search_and_store_lists_do_not_prove_order_totals(self):
        for kind in ('search', 'store_list', 'unknown'):
            with self.subTest(kind=kind):
                m = copy.deepcopy(self.manifest)
                m['captures'][0]['source_kind'] = kind
                self.assertTrue(any('insufficient' in s for s in self.check(m)))

    def test_each_visual_requirement_is_mandatory(self):
        for check in CHECKS:
            with self.subTest(check=check):
                m = copy.deepcopy(self.manifest)
                m['captures'][0][check] = False
                self.assertTrue(any(check in s for s in self.check(m)))

    def test_external_seller_caption_cannot_replace_in_photo_seller(self):
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['seller_and_total_same_capture'] = False
        self.assertTrue(any('seller_and_total_same_capture' in s for s in self.check(m)))

    def test_actual_seller_identity_is_required(self):
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['seller_identity'] = ''
        self.assertTrue(any('actual seller identity' in s for s in self.check(m)))

    def test_unrelated_navigation_or_ads_prevent_clean_capture_pass(self):
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['unrelated_page_chrome_excluded'] = False
        self.assertTrue(any('unrelated_page_chrome_excluded' in s for s in self.check(m)))

    def test_other_cart_goods_and_mixed_totals_are_rejected(self):
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['only_quoted_product_visible'] = False
        self.assertTrue(any('only_quoted_product_visible' in s for s in self.check(m)))

    def test_render_or_source_change_invalidates_review(self):
        for kind in ('original', 'render'):
            with self.subTest(kind=kind):
                p = self.base / (kind + '.png')
                old = p.read_bytes()
                p.write_bytes(b'changed')
                self.assertTrue(any(kind + ' file' in s for s in self.check()))
                p.write_bytes(old)

    def test_required_cart_accepts_cart_and_rejects_other_source_types(self):
        for kind in ('product_detail', 'vendor_quote'):
            with self.subTest(kind=kind):
                m = copy.deepcopy(self.manifest)
                m['captures'][0]['source_kind'] = kind
                self.assertTrue(any('required cart capture' in s for s in review_issues(self.doc, m, self.base, require_cart=True)))
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['source_kind'] = 'cart'
        self.assertEqual(review_issues(self.doc, m, self.base, require_cart=True), [])

    def test_required_cart_picture_ids_are_checked(self):
        self.assertTrue(any('required cart capture' in s for s in review_issues(self.doc, self.manifest, self.base, cart_picture_ids=('42',))))
        self.assertTrue(any('missing from document' in s for s in review_issues(self.doc, self.manifest, self.base, cart_picture_ids=('unknown',))))
        self.assertTrue(any('duplicates' in s for s in review_issues(self.doc, self.manifest, self.base, cart_picture_ids=('42','42'))))
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['source_kind'] = 'cart'
        self.assertEqual(review_issues(self.doc, m, self.base, cart_picture_ids=('42',)), [])

    def test_document_change_invalidates_review(self):
        self.manifest['document_sha256'] = 'stale'
        self.assertTrue(any('hash mismatch' in s for s in self.check()))

    def test_missing_capture_or_wrong_picture_id_is_rejected(self):
        m = copy.deepcopy(self.manifest)
        m['captures'] = []
        self.assertTrue(self.check(m))
        m = copy.deepcopy(self.manifest)
        m['captures'][0]['picture_id'] = 'wrong'
        self.assertTrue(self.check(m))


if __name__ == '__main__':
    unittest.main()
