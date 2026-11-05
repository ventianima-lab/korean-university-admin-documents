"""Synthetic baseline-to-output attachment list protection checks."""
import copy, hashlib, json, subprocess, sys, tempfile, unittest, xml.etree.ElementTree as ET
from pathlib import Path
from zipfile import ZipFile
import verify_required_packet as packet

class AttachmentTemplate(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
  self.before=self.root/"source.hwpx";self.after=self.root/"saved.hwpx"
  self.source=[f"  {i}. Document {i} Long --- {i}부."+(" 끝." if i==4 else "") for i in range(1,5)]
  self.output=[x.replace(f"Document {i} Long",f"Doc {i}") for i,x in enumerate(self.source,1)]
  self.make(self.before,self.source);self.make(self.after,self.output)
  self.mapping={"source":str(self.before),"target":str(self.after),"source_sha256":hashlib.sha256(self.before.read_bytes()).hexdigest(),"paragraphs":[]}
  for index,text in enumerate(self.source):
   old=f"Document {index+1} Long";start=text.index(old)
   self.mapping["paragraphs"].append({"source":{"section":"Contents/section0.xml","paragraph":index},"target":{"section":"Contents/section0.xml","paragraph":index},"titles":[{"start":start,"end":start+len(old),"old":old,"new":f"Doc {index+1}","authorization":"synthetic explicit title change"}]})
 def make(self,path,lines):
  root=ET.Element(packet.HP+"sec")
  for line in lines:
   p=ET.SubElement(root,packet.HP+"p");run=ET.SubElement(p,packet.HP+"run");ET.SubElement(run,packet.HP+"t").text=line
  with ZipFile(path,"w") as z:z.writestr("Contents/section0.xml",ET.tostring(root,encoding="utf-8"))
 def test_authorized_titles_pass(self):self.assertEqual(packet.check_attachment_template(self.mapping),[])
 def test_all_separator_deletion_fails(self):
  self.make(self.after,[x.replace("--- ","") for x in self.output]);self.assertEqual(len(packet.check_attachment_template(self.mapping)),4)
 def test_space_count_number_and_end_fail(self):
  for old,new in [("  1."," 1."),("1부.","2부."),("  1.","  9."),("끝.","종료.")]:
   with self.subTest(old=old,new=new):
    self.make(self.after,[x.replace(old,new) for x in self.output]);self.assertTrue(packet.check_attachment_template(self.mapping))
 def test_malformed_mapping_and_hash_fail_closed(self):
  for key in ("bad_hash","overlap","wrong_old","missing_authorization","same_path"):
   m=copy.deepcopy(self.mapping)
   if key=="bad_hash":m["source_sha256"]="0"*64
   if key=="overlap":m["paragraphs"][0]["titles"].append(copy.deepcopy(m["paragraphs"][0]["titles"][0]))
   if key=="wrong_old":m["paragraphs"][0]["titles"][0]["old"]="wrong"
   if key=="missing_authorization":m["paragraphs"][0]["titles"][0]["authorization"]=""
   if key=="same_path":m["target"]=m["source"]
   with self.subTest(key=key),self.assertRaises(ValueError):packet.check_attachment_template(m)
 def test_cli_flag_validates_real_saved_hwpx_and_legacy_invocation(self):
  manifest={"requirements":[{"id":"form","source":"synthetic"}],"artifacts":[{"id":"form","status":"ready","paths":[str(Path(__file__))],"verification":"synthetic"}],"expense_reviews":[{"category":"example","source":"synthetic","items":[{"label":"form","status":"required","requirement_id":"form"}]}],"attachment_template_check":self.mapping}
  path=self.root/"manifest.json";path.write_text(json.dumps(manifest),encoding="utf-8")
  command=[sys.executable,str(Path(packet.__file__)),str(path)]
  for suffix in ([],["--attachment-template-check"]):
   result=subprocess.run(command+suffix,capture_output=True,text=True,encoding="utf-8");self.assertEqual(result.returncode,0,result.stderr)
  self.make(self.after,[x.replace("--- ","") for x in self.output])
  result=subprocess.run(command+["--attachment-template-check"],capture_output=True,text=True,encoding="utf-8")
  self.assertEqual(result.returncode,1);self.assertIn("attachment_template_text_changed",result.stdout)
 def test_title_span_cannot_swallow_fixed_separator(self):
  m=copy.deepcopy(self.mapping);item=m["paragraphs"][0]["titles"][0]
  item["end"]+=4;item["old"]=self.source[0][item["start"]:item["end"]]
  with self.assertRaises(ValueError):packet.check_attachment_template(m)
 def test_unchanged_line_without_replacements(self):
  self.make(self.after,self.source);m=copy.deepcopy(self.mapping)
  for p in m["paragraphs"]:p["titles"]=[]
  self.assertEqual(packet.check_attachment_template(m),[])
if __name__=="__main__":unittest.main()
