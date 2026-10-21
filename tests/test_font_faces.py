"""Synthetic font semantics checks; no institutional document data."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('fonts', ROOT / 'skills/hancom-hwpx-documents/scripts/verify_font_faces.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


class FontTests(unittest.TestCase):
    def check(self, reference='8', latin='8', anchor='Title', count=1, paragraph=False):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'form.hwpx'
            header = '<head xmlns:h="http://www.hancom.co.kr/hwpml/2011/head">' + ''.join(f'<h:fontface lang="{lang}"><h:font id="8" face="Required Face"/><h:font id="3" face="Fallback Face"/></h:fontface>' for lang in ['HANGUL','LATIN']) + f'<h:charPr id="5"><h:fontRef hangul="{reference}" latin="{latin}"/></h:charPr></head>'
            section = '<section xmlns:p="http://www.hancom.co.kr/hwpml/2011/paragraph"><p:p><p:run charPrIDRef="5"><p:t>Ti</p:t></p:run><p:run charPrIDRef="5"><p:t>tle</p:t></p:run></p:p><p:p><p:run charPrIDRef="5"><p:t>Reference to Title</p:t></p:run></p:p></section>'
            with ZipFile(path, 'w') as z:
                z.writestr('Contents/header.xml',header)
                z.writestr('Contents/section0.xml',section)
            return M.verify(path, {'fonts':[dict(text=anchor,expected_face='Required Face',expected_occurrences=count,source='Synthetic source',match='paragraph' if paragraph else 'substring')]})

    def test_resolved_face_with_remapped_ids_and_split_runs(self):
        self.assertEqual(self.check(paragraph=True)[0]['occurrences'],1)

    def test_unused_required_font_does_not_pass(self):
        with self.assertRaisesRegex(ValueError,'Resolved font'):
            self.check(reference='3',paragraph=True)

    def test_latin_mapping_checked_independently(self):
        with self.assertRaisesRegex(ValueError,'latin'):
            self.check(latin='3',paragraph=True)

    def test_missing_anchor_rejected(self):
        with self.assertRaisesRegex(ValueError,'occurrence'):
            self.check(anchor='Missing')

    def test_all_occurrences_checked(self):
        self.assertEqual(self.check(count=2)[0]['occurrences'],2)

    def test_title_not_confused_with_reference_sentence(self):
        with self.assertRaisesRegex(ValueError,'occurrence'):
            self.check(count=1)


if __name__=='__main__':
    unittest.main()
