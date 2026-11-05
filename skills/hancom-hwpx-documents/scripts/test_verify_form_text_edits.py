"""Synthetic HWPX format-preservation behavior."""
import copy, hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from zipfile import ZipFile
import verify_form_text_edits as v
class FormPreservation(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.source=self.root/"a.hwpx";self.target=self.root/"b.hwpx"
  self.package(self.source,"Long title");self.package(self.target,"Short")
  self.spec={"source":str(self.source),"target":str(self.target),"source_sha256":v.digest(self.source),"edits":[{"section":"Contents/section0.xml","text_index":0,"old":"Long title","new":"Short","authorization":"synthetic title instruction"}]}
 def package(self,path,title,sep=" --- ",number="1.",space=" ",style="7",table="1",approval="Approval",line="cache",dirty="0",other="unchanged"):
  xml=f'<hs:sec xmlns:hs="urn:section" xmlns:hp="{v.HP[1:-1]}"><hp:p><hp:run charPrIDRef="{style}"><hp:t>{title}</hp:t></hp:run><hp:linesegarray><hp:seg>{line}</hp:seg></hp:linesegarray></hp:p><hp:p><hp:run><hp:t>{number}{space}{sep}1부.</hp:t></hp:run><hp:tbl id="{table}"><hp:tr><hp:tc dirty="{dirty}"><hp:p><hp:run><hp:t>{approval}</hp:t></hp:run></hp:p></hp:tc></hp:tr></hp:tbl></hp:p></hs:sec>'
  with ZipFile(path,"w") as z:z.writestr("Contents/section0.xml",xml);z.writestr("Contents/header.xml",other);z.writestr("mimetype","application/hwp+zip")
 def test_authorized_text_and_layout_cache_pass(self):
  self.package(self.target,"Short",line="new cache");self.assertEqual(v.verify(self.spec)["status"],"PASS")
 def test_unrequested_form_changes_fail(self):
  for changes in ({"sep":" "},{"number":"2."},{"space":"  "},{"style":"8"},{"table":"2"},{"approval":"Removed"},{"other":"changed"}):
   with self.subTest(changes=changes):
    self.package(self.target,"Short",**changes)
    with self.assertRaises(ValueError):v.verify(self.spec)
 def test_cli_honors_inventory_and_rejects_format_change(self):
  inventory=self.root/"spec.json";inventory.write_text(json.dumps(self.spec),encoding="utf-8")
  cmd=[sys.executable,str(Path(v.__file__)),str(inventory)]
  self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
  self.package(self.target,"Short",sep=" ")
  self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)
 def test_invalid_authorization_or_stale_snapshot_fail(self):
  for key in ("authorization","source_sha256","wrong_old"):
   spec=copy.deepcopy(self.spec)
   if key=="authorization":spec["edits"][0][key]=""
   elif key=="source_sha256":spec[key]="0"*64
   else:spec["edits"][0]["old"]="old wrong"
   with self.subTest(key=key),self.assertRaises(ValueError):v.verify(spec)
if __name__=="__main__":unittest.main()
