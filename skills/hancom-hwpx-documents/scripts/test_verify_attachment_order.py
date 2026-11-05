"""Synthetic attachment order, grouped units, count and compatibility tests."""
import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET

import verify_required_packet as v


class AttachmentOrder(unittest.TestCase):
    def setUp(self):
        self.scratch=Path(tempfile.gettempdir()).resolve()
        self.root=Path(tempfile.mkdtemp(prefix='attachment-order-',dir=self.scratch))
        if self.root.resolve().parent != self.scratch: raise RuntimeError('unsafe scratch')
        self.addCleanup(self.clean)
        self.letter=self.root/'01_letter.hwpx'
        self.paths=[self.letter]+[self.root/f'{i:02d}_attachment.dat' for i in range(2,5)]
        for p in self.paths[1:]:p.write_bytes(b'synthetic document')
        self.lines=['붙임  1. Plan --- 1부.','      2. Alpha·Beta --- 각 1부.','      3. Quote --- 2부. 끝.']
        self.write_letter(self.lines)
        self.entries=[self.entry('plan','Plan',0,['plan']),self.entry('a','Alpha',1,['doc']),
                      self.entry('b','Beta',2,['doc']),self.entry('quote','Quote',3,['copy1','copy2'])]
        self.paragraphs=[self.paragraph(0,'붙임  1. ','Plan --- 1부.',['plan']),
                         self.paragraph(1,'      2. ','Alpha·Beta --- 각 1부.',['a','b']),
                         self.paragraph(2,'      3. ','Quote --- 2부. 끝.',['quote'])]
        self.check={'letter':str(self.letter),'start_marker':'붙임','end_marker':'끝.',
                    'paragraphs':self.paragraphs,'entries':self.entries,'actual_files':[str(p) for p in self.paths]}
        def unit(key,i,loc):return {'entry':key,'path':str(self.paths[i]),'location':loc,'evidence':'independent synthetic unit'}
        self.order={'letter_sha256':self.hash(self.letter),
                    'authority':{'kind':'numbered_files','reference':'synthetic instruction says numbered packet order'},
                    'packet_files':[{'path':str(p),'sha256':self.hash(p),'evidence':'independent synthetic packet'} for p in self.paths],
                    'units':[unit('plan',0,'plan'),unit('a',1,'doc'),unit('b',2,'doc'),unit('quote',3,'copy1'),unit('quote',3,'copy2')]}

    def clean(self):
        p=self.root.resolve()
        if p.parent != self.scratch or not p.name.startswith('attachment-order-'):raise RuntimeError('unsafe cleanup')
        shutil.rmtree(p)

    @staticmethod
    def hash(p):return hashlib.sha256(p.read_bytes()).hexdigest()

    def write_letter(self,lines):
        root=ET.Element(v.HP+'sec')
        for text in lines:
            p=ET.SubElement(root,v.HP+'p');run=ET.SubElement(p,v.HP+'run');ET.SubElement(run,v.HP+'t').text=text
        with ZipFile(self.letter,'w') as z:z.writestr('Contents/section0.xml',ET.tostring(root,encoding='utf-8'))

    def refresh_letter_hash(self):
        digest=self.hash(self.letter);self.order['letter_sha256']=digest;self.order['packet_files'][0]['sha256']=digest

    def entry(self,key,title,i,locations):
        return {'id':key,'title':title,'role':'other','members':[{'path':str(self.paths[i]),'locations':locations,'evidence':'synthetic unit'}]}

    def paragraph(self,i,prefix,body,ids):
        return {'section':'Contents/section0.xml','paragraph':i,'segments':[{'kind':'context','text':prefix},
                {'kind':'item','text':body,'entries':ids}]}

    def issue_codes(self):return {x['problem'] for x in v.check_attachment_order(self.check,self.order)}

    def test_grouped_units_and_two_copies_pass(self):
        self.assertEqual(v.check_attachment_list(self.check),[])
        self.assertEqual(v.check_attachment_order(self.check,self.order),[])

    def test_inversion_passes_legacy_check_but_order_check_rejects(self):
        self.lines[1]='      2. Beta·Alpha --- 각 1부.';self.write_letter(self.lines);self.refresh_letter_hash()
        self.check['paragraphs'][1]=self.paragraph(1,'      2. ','Beta·Alpha --- 각 1부.',['b','a'])
        self.assertEqual(v.check_attachment_list(self.check),[])
        self.assertIn('attachment_role_order_mismatch',self.issue_codes())

    def test_actual_file_order_is_not_only_a_set(self):
        self.check['actual_files'][1:3]=reversed(self.check['actual_files'][1:3])
        self.assertEqual(v.check_attachment_list(self.check),[])
        self.assertIn('attachment_actual_file_order_mismatch',self.issue_codes())

    def test_bad_numbered_sequence_is_rejected(self):
        self.order['packet_files'][1:3]=reversed(self.order['packet_files'][1:3])
        self.assertIn('attachment_numbered_file_order_mismatch',self.issue_codes())

    def test_mapped_unit_omission_and_incorrect_bundle_order_fail(self):
        omitted=copy.deepcopy(self.order);omitted['units'].pop()
        self.assertIn('attachment_order_unit_mapping_mismatch',{x['problem'] for x in v.check_attachment_order(self.check,omitted)})
        swapped=copy.deepcopy(self.order);swapped['units'][-2:]=reversed(swapped['units'][-2:])
        self.assertIn('attachment_bundle_member_order_mismatch',{x['problem'] for x in v.check_attachment_order(self.check,swapped)})

    def test_roles_mapped_to_wrong_files_fail_independent_unit_map(self):
        self.check['entries'][1]['members'],self.check['entries'][2]['members']=(
            self.check['entries'][2]['members'],self.check['entries'][1]['members'])
        self.assertEqual(v.check_attachment_list(self.check),[])
        self.assertIn('attachment_order_unit_mapping_mismatch',self.issue_codes())

    def test_wrong_copy_count_still_fails_existing_checker(self):
        self.lines[2]='      3. Quote --- 1부. 끝.';self.write_letter(self.lines);self.refresh_letter_hash()
        self.check['paragraphs'][2]=self.paragraph(2,'      3. ','Quote --- 1부. 끝.',['quote'])
        self.assertIn('attachment_count_mismatch',{x['problem'] for x in v.check_attachment_list(self.check)})

    def test_hash_and_order_authority_are_required(self):
        self.order['packet_files'][1]['sha256']='0'*64
        self.assertIn('attachment_order_file_hash_mismatch',self.issue_codes())
        self.order['authority']['reference']=''
        with self.assertRaises(ValueError):v.check_attachment_order(self.check,self.order)

    def test_explicit_non_numeric_order_is_preserved(self):
        self.lines[1]='      2. Beta·Alpha --- 각 1부.';self.write_letter(self.lines);self.refresh_letter_hash()
        self.check['paragraphs'][1]=self.paragraph(1,'      2. ','Beta·Alpha --- 각 1부.',['b','a'])
        self.check['actual_files'][1:3]=reversed(self.check['actual_files'][1:3])
        self.order['packet_files'][1:3]=reversed(self.order['packet_files'][1:3])
        self.order['units'][1:3]=reversed(self.order['units'][1:3])
        self.order['authority']={'kind':'explicit','reference':'synthetic user explicitly chooses this order'}
        self.assertEqual(v.check_attachment_list(self.check),[])
        self.assertEqual(v.check_attachment_order(self.check,self.order),[])

    def test_cli_order_gate_is_opt_in_and_requires_content_gate(self):
        self.lines[1]='      2. Beta·Alpha --- 각 1부.';self.write_letter(self.lines);self.refresh_letter_hash()
        self.check['paragraphs'][1]=self.paragraph(1,'      2. ','Beta·Alpha --- 각 1부.',['b','a'])
        manifest={'requirements':[{'id':'form','source':'synthetic'}],
                  'artifacts':[{'id':'form','status':'ready','paths':[str(Path(__file__))],'verification':'synthetic'}],
                  'expense_reviews':[{'category':'x','source':'synthetic','items':[{'label':'form','status':'required','requirement_id':'form'}]}],
                  'attachment_check':self.check,'attachment_order_check':self.order}
        mf=self.root/'private.json';mf.write_text(json.dumps(manifest),encoding='utf-8')
        cmd=[sys.executable,str(Path(v.__file__)),str(mf)]
        self.assertEqual(subprocess.run(cmd+['--attachment-check'],capture_output=True).returncode,1)
        self.assertEqual(subprocess.run(cmd+['--attachment-check','--attachment-order-check'],capture_output=True).returncode,1)
        self.assertEqual(subprocess.run(cmd+['--attachment-order-check'],capture_output=True).returncode,2)
        del manifest['attachment_order_check']
        mf.write_text(json.dumps(manifest),encoding='utf-8')
        self.assertEqual(subprocess.run(cmd+['--attachment-check'],capture_output=True).returncode,0)


if __name__=='__main__':unittest.main()
