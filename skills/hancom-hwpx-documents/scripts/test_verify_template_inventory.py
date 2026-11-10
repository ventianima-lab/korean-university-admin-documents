"""Source-driven form input coverage; synthetic fixtures only."""
import copy, hashlib, json, subprocess, sys, tempfile, unittest, xml.etree.ElementTree as E
from pathlib import Path
from zipfile import ZipFile
import verify_input_coverage as v
H="{http://www.hancom.co.kr/hwpml/2011/paragraph}"

class TemplateInventory(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.template=self.root/"template.hwpx";self.output=self.root/"output.hwpx";self.evidence=self.root/"evidence.txt"
  self.make(self.template,[("Indicator","example"),("Notes",""),("Signature","")]);self.make(self.output,[("Indicator","planned goal"),("Notes","supported note"),("Signature","")]);self.evidence.write_text("independent evidence",encoding="utf-8")
  self.ev=[{"kind":"document","path":str(self.evidence),"sha256":self.hash(self.evidence),"location":"example field"}]
  self.m={"template":{"path":str(self.template),"sha256":self.hash(self.template),"section":"Contents/section0.xml","table":0},"scope":[{"row_start":0,"row_end":2,"input_cols":[1]}],"fields":[self.field(0,"Indicator","known","planned goal"),self.field(1,"Notes","known","supported note"),self.field(2,"Signature","controlled",None)]}
 def hash(self,p):return hashlib.sha256(p.read_bytes()).hexdigest()
 def field(self,row,label,status,expected):
  x={"source":{"row":row,"col":1,"label_col":0,"label":label},"target":{"section":"Contents/section0.xml","table":0,"row":row,"col":1,"label_col":0,"label":label},"status":status,"reason":"independently classified"}
  if expected is not None:x.update(expected=expected,evidence=copy.deepcopy(self.ev),value_kind="plan")
  return x
 def make(self,path,lines):
  root=E.Element(H+"sec");p=E.SubElement(root,H+"p");run=E.SubElement(p,H+"run");tb=E.SubElement(run,H+"tbl")
  for index,vals in enumerate(lines):
   tr=E.SubElement(tb,H+"tr")
   for col,text in enumerate(vals):
    cell=E.SubElement(tr,H+"tc");E.SubElement(cell,H+"cellAddr",rowAddr=str(index),colAddr=str(col));sub=E.SubElement(cell,H+"subList");par=E.SubElement(sub,H+"p");run=E.SubElement(par,H+"run");E.SubElement(run,H+"t").text=text
  with ZipFile(path,"w") as z:z.writestr("Contents/section0.xml",E.tostring(root,encoding="utf-8"))
 def check(self):return v.verify_template_inventory(self.output,self.m)
 def test_original_seal_missing_or_changed_cannot_pass(self):
  seal=b'GIF89a-synthetic-issuer-object'
  with ZipFile(self.template,'a') as z:z.writestr('BinData/seal.gif',seal)
  self.m['template']['sha256']=self.hash(self.template)
  self.m['identity_assets']=[{'source_member':'BinData/seal.gif','target_member':'BinData/seal.gif','sha256':hashlib.sha256(seal).hexdigest(),'role':'issuer seal','recognition':'recognized'}]
  with self.assertRaisesRegex(ValueError,'asset missing'):self.check()
  with ZipFile(self.output,'a') as z:z.writestr('BinData/seal.gif',b'different issuer')
  with self.assertRaisesRegex(ValueError,'not preserved'):self.check()
  self.make(self.output,[("Indicator","planned goal"),("Notes","supported note"),("Signature","")])
  with ZipFile(self.output,'a') as z:z.writestr('BinData/seal.gif',seal)
  self.assertEqual(self.check()['status'],'PASS')
  self.m['identity_assets'][0]['recognition']='unresolved'
  self.assertEqual(self.check()['status'],'PASS') # byte preservation, not semantic recognition
 def test_complete_mapping_passes(self):self.assertEqual(self.check()["mapped_fields"],3)
 def test_omitted_source_field_fails_even_if_output_is_filled(self):
  self.m["fields"].pop(0)
  with self.assertRaisesRegex(ValueError,"omitted"):self.check()
 def test_known_blank_and_wrong_value_fail(self):
  for x in ("","different"):
   self.make(self.output,[("Indicator",x),("Notes","supported note"),("Signature","")])
   with self.subTest(x=x),self.assertRaises(ValueError):self.check()
 def test_controlled_value_cannot_be_fabricated(self):
  self.make(self.output,[("Indicator","planned goal"),("Notes","supported note"),("Signature","invented")])
  with self.assertRaisesRegex(ValueError,"not blank"):self.check()
 def test_user_preserved_signature_can_be_verified(self):
  self.make(self.output,[("Indicator","planned goal"),("Notes","supported note"),("Signature","existing")]);x=self.m["fields"][2];x.update(status="preserved",expected="existing",value_kind="user_preserved",evidence=copy.deepcopy(self.ev));self.assertEqual(self.check()["status"],"PASS")
 def test_hash_evidence_label_and_scope_fail_closed(self):
  for failure in ("template_hash","evidence_hash","target_label","duplicate","source_scope","self_evidence","missing_kind"):
   m=copy.deepcopy(self.m)
   if failure=="template_hash":m["template"]["sha256"]="0"*64
   if failure=="evidence_hash":m["fields"][0]["evidence"][0]["sha256"]="0"*64
   if failure=="target_label":m["fields"][0]["target"]["label"]="incorrect"
   if failure=="duplicate":m["fields"].append(copy.deepcopy(m["fields"][0]))
   if failure=="source_scope":m["scope"][0]["row_end"]=3
   if failure=="self_evidence":m["fields"][0]["evidence"][0].update(path=str(self.output),sha256=self.hash(self.output))
   if failure=="missing_kind":del m["fields"][0]["value_kind"]
   with self.subTest(failure=failure),self.assertRaises((ValueError,KeyError)):v.verify_template_inventory(self.output,m)
 def test_unconfirmed_requires_checked_sources(self):
  self.make(self.output,[("Indicator","planned goal"),("Notes",""),("Signature","")]);x=self.m["fields"][1];x.update(status="unconfirmed",lookups=["source A","source B"]);self.assertEqual(self.check()["status"],"PASS");x["lookups"]=["source A","source A"]
  with self.assertRaises(ValueError):self.check()
 def test_cli_mode_and_existing_mode_still_work(self):
  f=self.root/"manifest.json";f.write_text(json.dumps(self.m),encoding="utf-8");cmd=[sys.executable,str(Path(v.__file__)),str(self.output),str(f),"--template-inventory"]
  self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
  legacy={"cells":[{"section":"Contents/section0.xml","table":0,"row":2,"col":1,"status":"controlled","reason":"signer-controlled"}]};f.write_text(json.dumps(legacy),encoding="utf-8")
  self.assertEqual(subprocess.run(cmd[:-1],capture_output=True).returncode,0)
  f.write_text(json.dumps(self.m),encoding="utf-8");self.make(self.output,[("Indicator",""),("Notes","supported note"),("Signature","")]);self.assertNotEqual(subprocess.run(cmd,capture_output=True).returncode,0)
if __name__=="__main__":unittest.main()
