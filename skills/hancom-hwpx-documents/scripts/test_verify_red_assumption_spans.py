"""Synthetic regression tests; no user documents or private data."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.sax.saxutils import escape

import verify_red_assumption_spans as gate


class RedSpans(unittest.TestCase):
    def setUp(self):
        self.scratch = Path(tempfile.gettempdir()).resolve()
        self.root = Path(tempfile.mkdtemp(prefix='red-span-test-', dir=self.scratch))
        if self.root.resolve().parent != self.scratch:
            raise RuntimeError('generated test directory escaped scratch')
        self.addCleanup(self.clean_scratch)
        self.before = self.root / 'before.hwpx'
        self.after = self.root / 'after.hwpx'
        self.text = 'Title: option; approved: 15'
        self.start = self.text.index('option')
        self.end = self.start + len('option')
        self.confirmed = self.text.index('15')
        self.write(self.before, added=False)
        self.write(self.after, red=set(range(self.start, self.end)))
        self.spec = self.inventory()

    def clean_scratch(self):
        resolved = self.root.resolve()
        if resolved.parent != self.scratch or not resolved.name.startswith('red-span-test-'):
            raise RuntimeError('refusing recursive cleanup outside scratch')
        shutil.rmtree(resolved)

    def write(self, path, red=(), text=None, font='0', table='1', preexisting='#FF0000',
              added=True, style_size='1000', inline=False, other='unchanged', normal='#000000'):
        text = self.text if text is None else text
        red = set(red)
        props = (f'<hh:charPr id="0" height="1000" textColor="{normal}"><hh:fontRef hangul="0" latin="0"/></hh:charPr>'
                 f'<hh:charPr id="1" height="1000" textColor="{preexisting}"><hh:fontRef hangul="0" latin="0"/></hh:charPr>')
        if added:
            props += f'<hh:charPr id="2" height="{style_size}" textColor="#FF0000"><hh:fontRef hangul="{font}" latin="0"/></hh:charPr>'
        header = ('<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head">'
                  '<hh:fontfaces><hh:fontface lang="HANGUL"><hh:font id="0" face="Generic"/><hh:font id="1" face="Other"/></hh:fontface></hh:fontfaces>'
                  f'<hh:charProperties>{props}</hh:charProperties></hh:head>')
        runs = []
        for n, ch in enumerate(text):
            style = '2' if n in red else '0'
            runs.append(f'<hp:run charPrIDRef="{style}"><hp:t>{escape(ch)}</hp:t></hp:run>')
        if inline:
            runs.append('<hp:run charPrIDRef="0"><hp:t>x<hp:lineBreak/>y</hp:t></hp:run>')
        table_xml = (f'<hp:run charPrIDRef="0"><hp:tbl id="{table}"><hp:tr><hp:tc><hp:p>'
                     '<hp:run charPrIDRef="1"><hp:t>Fixed --- 1</hp:t></hp:run>'
                     '</hp:p></hp:tc></hp:tr></hp:tbl></hp:run>')
        section = ('<hs:sec xmlns:hs="urn:synthetic" xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                   '<hp:p>' + ''.join(runs) + table_xml + '</hp:p></hs:sec>')
        with ZipFile(path, 'w') as z:
            z.writestr('mimetype', 'application/hwp+zip')
            z.writestr('Contents/header.xml', header)
            z.writestr('Contents/section0.xml', section)
            z.writestr('Contents/content.hpf', other)

    def inventory(self):
        def entry(start, end, provenance):
            return dict(section='Contents/section0.xml', paragraph=0, start=start, end=end,
                        text=self.text[start:end], provenance=provenance, evidence='independent synthetic source')
        return {'before_sha256':gate.sha(self.before), 'after_sha256':gate.sha(self.after),
                'red_instruction':'explicit synthetic user instruction', 'red_color':'#FF0000',
                'values':[entry(self.start,self.end,'assistant_unconfirmed'),
                          entry(self.confirmed,self.confirmed+2,'user_confirmed'),
                          entry(0,5,'fixed_form')]}

    def refresh(self):
        self.spec['after_sha256'] = gate.sha(self.after)

    def test_correct_span_and_existing_red_fixed_text_pass(self):
        result = gate.verify(self.before, self.after, self.spec)
        self.assertEqual(result['status'], 'PASS')
        self.assertEqual(result['assumption_characters'], len('option'))

    def test_standing_preference_preserves_blue_fixed_text(self):
        self.write(self.before, added=False, preexisting='#0000FF', normal='#0000FF')
        self.write(self.after, red=range(self.start, self.end), preexisting='#0000FF', normal='#0000FF')
        self.spec = self.inventory()
        self.spec['red_instruction'] = 'synthetic standing instruction for later documents'
        self.spec['red_instruction_scope'] = 'standing_preference'
        self.assertEqual(gate.verify(self.before, self.after, self.spec)['status'], 'PASS')

    def test_standing_mode_cannot_normalize_fixed_blue_to_black(self):
        self.write(self.before, added=False, preexisting='#0000FF')
        self.write(self.after, red=range(self.start, self.end), preexisting='#000000')
        self.spec = self.inventory()
        self.spec['red_instruction_scope'] = 'standing_preference'
        with self.assertRaisesRegex(ValueError, 'existing character style definition changed'):
            gate.verify(self.before, self.after, self.spec)

    def test_unknown_scope_and_missing_standing_reference_fail(self):
        self.spec['red_instruction_scope'] = 'automatic_without_user_instruction'
        with self.assertRaisesRegex(ValueError, 'red_instruction_scope'):
            gate.verify(self.before, self.after, self.spec)
        self.spec['red_instruction_scope'] = 'standing_preference'
        self.spec['red_instruction'] = ''
        with self.assertRaisesRegex(ValueError, 'standing user instruction reference'):
            gate.verify(self.before, self.after, self.spec)

    def test_missing_one_assumption_character_fails(self):
        self.write(self.after, red=range(self.start+1,self.end)); self.refresh()
        with self.assertRaisesRegex(ValueError,'missing requested red'):
            gate.verify(self.before,self.after,self.spec)

    def test_red_spill_to_neighbor_or_confirmed_value_fails(self):
        for extra in ({self.start-1},{self.end},{self.confirmed}):
            with self.subTest(extra=extra):
                self.write(self.after, red=set(range(self.start,self.end)) | extra); self.refresh()
                with self.assertRaisesRegex(ValueError,'outside authorized'):
                    gate.verify(self.before,self.after,self.spec)

    def test_omitted_assumption_inventory_does_not_excuse_red(self):
        self.spec['values'] = self.spec['values'][1:]
        with self.assertRaisesRegex(ValueError,'outside authorized'):
            gate.verify(self.before,self.after,self.spec)

    def test_font_or_size_change_fails(self):
        for change in ({'font':'1'},{'style_size':'900'}):
            with self.subTest(change=change):
                self.write(self.after,red=range(self.start,self.end),**change); self.refresh()
                with self.assertRaisesRegex(ValueError,'font or other'):
                    gate.verify(self.before,self.after,self.spec)

    def test_original_style_table_body_and_package_are_protected(self):
        for change in ({'table':'2'},{'preexisting':'#000000'},
                       {'text':self.text+' pending'},{'other':'changed'}):
            with self.subTest(change=change):
                self.write(self.after,red=range(self.start,self.end),**change); self.refresh()
                with self.assertRaises(ValueError):
                    gate.verify(self.before,self.after,self.spec)

    def test_missing_instruction_stale_hash_and_overlap_fail(self):
        for change in ('instruction','hash','overlap'):
            spec=copy.deepcopy(self.spec)
            if change == 'instruction': spec['red_instruction']=''
            if change == 'hash': spec['before_sha256']='0'*64
            if change == 'overlap': spec['values'].append(copy.deepcopy(spec['values'][0]))
            with self.subTest(change=change), self.assertRaises(ValueError):
                gate.verify(self.before,self.after,spec)

    def test_wrong_expected_text_or_out_of_range_fails(self):
        for change in ('text','range'):
            spec=copy.deepcopy(self.spec)
            if change == 'text': spec['values'][0]['text']='other'
            else: spec['values'][0]['end']=999
            with self.subTest(change=change), self.assertRaises(ValueError):
                gate.verify(self.before,self.after,spec)

    def test_inline_control_fails_closed(self):
        self.write(self.after,red=range(self.start,self.end),inline=True); self.refresh()
        with self.assertRaisesRegex(ValueError,'unsupported inline'):
            gate.verify(self.before,self.after,self.spec)

    def test_cli_pass_and_failed_omission(self):
        manifest=self.root/'inventory.json'
        manifest.write_text(json.dumps(self.spec),encoding='utf-8')
        cmd=[sys.executable,str(Path(gate.__file__)),str(self.before),str(self.after),str(manifest)]
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.write(self.after,red=range(self.start+1,self.end)); self.refresh()
        manifest.write_text(json.dumps(self.spec),encoding='utf-8')
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)


if __name__ == '__main__':
    unittest.main()
