from __future__ import annotations
import copy, json, tempfile, unittest, zipfile
from pathlib import Path
from verify_same_page_pairs import HP, sha, verify

def pdf_write(path, pages):
    objects=[]
    def add(data): objects.append(data); return len(objects)
    catalog=add(b""); tree=add(b""); font=add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"); pageids=[]
    for lines in pages:
        stream=("BT /F1 12 Tf 36 760 Td "+" ".join("("+s+") Tj 0 -18 Td" for s in lines)+" ET").encode()
        content=add(b"<< /Length "+str(len(stream)).encode()+b" >>\nstream\n"+stream+b"\nendstream")
        pageids.append(add(f"<< /Type /Page /Parent {tree} 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 {font} 0 R >> >> /Contents {content} 0 R >>".encode()))
    objects[catalog-1]=f"<< /Type /Catalog /Pages {tree} 0 R >>".encode(); objects[tree-1]=("<< /Type /Pages /Count %d /Kids [%s] >>"%(len(pageids)," ".join(f"{i} 0 R" for i in pageids))).encode()
    data=bytearray(b"%PDF-1.4\n"); offsets=[0]
    for i,obj in enumerate(objects,1): offsets.append(len(data)); data.extend(f"{i} 0 obj\n".encode()+obj+b"\nendobj\n")
    start=len(data); data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for off in offsets[1:]: data.extend(f"{off:010d} 00000 n \n".encode())
    data.extend(f"trailer << /Size {len(offsets)} /Root {catalog} 0 R >>\nstartxref\n{start}\n%%EOF\n".encode()); path.write_bytes(data)

def write_hwpx(path, missing=False, changed=False, textchange=False):
    ns=f'xmlns:hp="{HP}"'; inner=[]
    for i in range(16-(1 if missing else 0)):
        marker=f"item{i//2}quote{i%2+1}" + ("changed" if textchange and i==0 else "")
        inner.append(f'<hp:p><hp:t>{marker}</hp:t><hp:pic id="{i}"><img binaryItemIDRef="im{i}"/></hp:pic></hp:p>')
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('Contents/section0.xml',f'<root {ns}>'.join(['',''.join(inner)+'</root>']))
        z.writestr('Contents/content.hpf', '<package xmlns:opf="urn:opf">'+''.join(f'<opf:item id="im{i}" href="BinData/{i}.png"/>' for i in range(16-(1 if missing else 0)))+'</package>')
        for i in range(16-(1 if missing else 0)): z.writestr(f'BinData/{i}.png',f'image{i}'+('X' if changed and i==0 else ''))

class SamePageTests(unittest.TestCase):
    def setUp(self):
        self.t=tempfile.TemporaryDirectory(); self.addCleanup(self.t.cleanup); self.d=Path(self.t.name); self.a=self.d/'a.hwpx'; self.b=self.d/'b.hwpx'; self.pdf=self.d/'p.pdf'
        write_hwpx(self.a); write_hwpx(self.b); pdf_write(self.pdf,[[f'item{i}quote1',f'item{i}quote2'] for i in range(8)])
        self.m={'document_sha256':sha(self.a),'baseline_sha256':sha(self.b),'pdf_sha256':sha(self.pdf),'pdf_export_from_document_sha256':sha(self.a),'pdf_export_verified':True,'pairs':[]}
        for i in range(8):
            self.m['pairs'].append({'picture_ids':[str(i*2),str(i*2+1)],'page':i+1,'markers':[f'item{i}quote1',f'item{i}quote2'],**dict.fromkeys(('both_pictures_on_page','labels_match_pictures','all_details_readable','no_clipping_or_overlap','same_item_quotes_1_and_2'),True)})
    def check(self): return verify(self.a,self.b,self.pdf,self.m,8)
    def test_16_captures_8_pairs_pass(self): self.assertEqual([],self.check())
    def test_split_physical_page_fails(self):
        pages=[[f'item{i}quote1',f'item{i}quote2'] for i in range(8)]; pages[0]=['item0quote1']; pages.append(['item0quote2']); pdf_write(self.pdf,pages); self.m['pdf_sha256']=sha(self.pdf); self.assertTrue(any('physical page' in x for x in self.check()))
    def test_unreadable_fails(self): self.m['pairs'][0]['all_details_readable']=False; self.assertTrue(any('all_details_readable' in x for x in self.check()))
    def test_missing_picture_fails(self): write_hwpx(self.a,missing=True); self.m['document_sha256']=sha(self.a); self.m['pdf_export_from_document_sha256']=sha(self.a); self.assertTrue(any('capture count' in x for x in self.check()))
    def test_changed_media_fails(self): write_hwpx(self.a,changed=True); self.m['document_sha256']=sha(self.a); self.m['pdf_export_from_document_sha256']=sha(self.a); self.assertTrue(any('media content' in x for x in self.check()))
    def test_changed_text_fails(self): write_hwpx(self.a,textchange=True); self.m['document_sha256']=sha(self.a); self.assertTrue(any('text differs' in x for x in self.check()))
    def test_stale_and_forged_pair_inventory_fail(self):
        self.m['pdf_sha256']='stale'; self.m['pairs'][0]['picture_ids']=['0','2']; self.assertTrue(any('mismatch' in x for x in self.check())); self.assertTrue(any('picture IDs' in x for x in self.check()))
    def test_missing_attestation_fails(self): self.m['pdf_export_verified']=False; self.assertTrue(any('export not visually' in x for x in self.check()))
    def test_authorized_exact_title_and_label_pass(self):
        self._changes(True)
        self.assertEqual([], self.check())
    def test_unauthorized_title_fails(self):
        self._changes(False)
        self.assertTrue(any('saved text differs' in x for x in self.check()))
    def test_wrong_exact_before_fails(self):
        self._changes(True); self.m['authorized_text_edits'][0]['before']='wrong'
        with self.assertRaises(ValueError): self.check()
    def test_amount_change_rejected_even_with_claimed_authorization(self):
        self._changes(True); self.m['authorized_text_edits'][0]['before']='100'; self.m['authorized_text_edits'][0]['kind']='prefix_quote_number'
        with self.assertRaises(ValueError): self.check()
    def _changes(self, authorized):
        # Insert a permitted standalone duplicate title and seller label into a synthetic 16-picture fixture.
        import xml.etree.ElementTree as ET
        def rewrite(path, final):
            with zipfile.ZipFile(path) as z: data={n:z.read(n) for n in z.namelist()}
            root=ET.fromstring(data['Contents/section0.xml']); node=root[0]
            title=ET.Element(f'{{{HP}}}t'); title.text='Example 비교견적'; seller=ET.Element(f'{{{HP}}}t'); seller.text='판매처: Example'
            node.insert(0,title); node.insert(1,seller)
            if final: node.remove(title); seller.text='비교견적 1 | 판매처: Example'
            data['Contents/section0.xml']=ET.tostring(root,encoding='utf-8')
            with zipfile.ZipFile(path,'w') as z:
                for name,value in data.items(): z.writestr(name,value)
        rewrite(self.b,False); rewrite(self.a,True)
        self.m.update(document_sha256=sha(self.a),baseline_sha256=sha(self.b),pdf_export_from_document_sha256=sha(self.a))
        if authorized:
            self.m['authorized_text_edits']=[dict(baseline_index=0,before='Example 비교견적',after='',kind='remove_duplicate_title',independently_reviewed=True,instruction_reference='user'),dict(baseline_index=1,before='판매처: Example',after='비교견적 1 | 판매처: Example',kind='prefix_quote_number',independently_reviewed=True,instruction_reference='user')]
    def test_protected_amount_cell_change_fails(self):
        import xml.etree.ElementTree as ET
        def add_cell(path, amount):
            with zipfile.ZipFile(path) as z: data={n:z.read(n) for n in z.namelist()}
            root=ET.fromstring(data['Contents/section0.xml']); table=ET.SubElement(root,f'{{{HP}}}tbl'); cell=ET.SubElement(table,f'{{{HP}}}tc'); t=ET.SubElement(cell,f'{{{HP}}}t'); t.text=amount
            data['Contents/section0.xml']=ET.tostring(root,encoding='utf-8')
            with zipfile.ZipFile(path,'w') as z:
                for name,value in data.items(): z.writestr(name,value)
        add_cell(self.b,'100'); add_cell(self.a,'200'); self.m.update(document_sha256=sha(self.a),baseline_sha256=sha(self.b),pdf_export_from_document_sha256=sha(self.a))
        self.assertTrue(any('table cells' in x for x in self.check()))
    def test_swapped_image_references_fail(self):
        import xml.etree.ElementTree as ET
        with zipfile.ZipFile(self.a) as z: data={n:z.read(n) for n in z.namelist()}
        root=ET.fromstring(data['Contents/section0.xml']); images=[x for x in root.iter() if x.get('binaryItemIDRef')]; images[0].set('binaryItemIDRef','im1'); images[1].set('binaryItemIDRef','im0'); data['Contents/section0.xml']=ET.tostring(root,encoding='utf-8')
        with zipfile.ZipFile(self.a,'w') as z:
            for name,value in data.items(): z.writestr(name,value)
        self.m.update(document_sha256=sha(self.a),pdf_export_from_document_sha256=sha(self.a)); self.assertTrue(any('binary contents or order' in x for x in self.check()))
if __name__=='__main__': unittest.main()
