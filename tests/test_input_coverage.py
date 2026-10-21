import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest
P=Path(__file__).resolve().parents[1]/'skills/hancom-hwpx-documents/scripts/verify_input_coverage.py'
spec=importlib.util.spec_from_file_location('coverage_gate',P);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class CoverageTest(unittest.TestCase):
 def setUp(self):
  self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.file=Path(self.tmp.name)/'form.hwpx'
  with ZipFile(self.file,'w') as z:z.writestr('Contents/section0.xml','<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:tbl><hp:tr><hp:tc><hp:subList><hp:p><hp:run><hp:t/></hp:run></hp:p></hp:subList><hp:cellAddr rowAddr="0" colAddr="0"/></hp:tc><hp:tc><hp:subList><hp:p><hp:run><hp:t>Member A</hp:t></hp:run></hp:p></hp:subList><hp:cellAddr rowAddr="0" colAddr="1"/></hp:tc></hp:tr></hp:tbl></sec>')
  self.blank=dict(section='Contents/section0.xml',table=0,row=0,col=0,status='controlled',reason='Actual participant signature')
 def test_complete(self):self.assertEqual(m.verify(self.file,{'cells':[self.blank]})['blank_cells'],1)
 def test_omitted_blank(self):
  with self.assertRaisesRegex(ValueError,'Unclassified'):m.verify(self.file,{'cells':[]})
 def test_missing_known_value(self):
  b=dict(self.blank,status='known',source='Independent roster',expected='Birth date')
  with self.assertRaisesRegex(ValueError,'mismatch'):m.verify(self.file,{'cells':[b]})
 def test_unconfirmed_first_source_only(self):
  b=dict(self.blank,status='unconfirmed',lookups=['Contact list'])
  with self.assertRaisesRegex(ValueError,'distinct'):m.verify(self.file,{'cells':[b]})
 def test_distinct_sources(self):
  b=dict(self.blank,status='unconfirmed',lookups=['Full roster checked','Authorized system access failed'])
  self.assertEqual(m.verify(self.file,{'cells':[b]})['status'],'PASS')
 def test_wrong_identity(self):
  b=dict(self.blank,col=1,status='known',source='Roster ID 001',expected='Member B')
  with self.assertRaisesRegex(ValueError,'mismatch'):m.verify(self.file,{'cells':[self.blank,b]})
 def test_duplicate_disposition(self):
  with self.assertRaisesRegex(ValueError,'Duplicate'):m.verify(self.file,{'cells':[self.blank,self.blank]})
if __name__=='__main__':unittest.main()
