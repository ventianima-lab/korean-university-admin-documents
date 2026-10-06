"""Exercise default rejection, authorized exceptions, and evidence-value mismatches."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_STORED
from xml.etree import ElementTree as E
from copy import deepcopy
import json,subprocess,sys

HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
H='{'+HP+'}'
def document(path,product='Model B',quantity='2개',total=22000,source='Store B',note='유사제품: 브랜드와 모델이 다름.',pictures=2):
 root=E.Element(H+'sec')
 texts=['Item | Model A | 수량 2개 | 총액 24,000원 | 출처 Store A',f'비교견적 1 | Item | {product} | 수량 {quantity} | 총액 {total:,}원 | 출처 {source}',note]
 for s in texts:
  p=E.SubElement(root,H+'p');run=E.SubElement(p,H+'run');E.SubElement(run,H+'t').text=s
 for _ in range(pictures):E.SubElement(E.SubElement(root,H+'pic'),H+'pos',{'treatAsChar':'1','flowWithText':'1'})
 with ZipFile(path,'w')as z:
  z.writestr('mimetype','application/hwp+zip',compress_type=ZIP_STORED)
  z.writestr('Contents/section0.xml',E.tostring(root))
def main():
 verifier=Path(__file__).with_name('verify_quote_hwpx.py')
 manifest={'authorization':'The user explicitly allowed similar products.','items':[{'item':'Item','main':{'product':'Model A','quantity':'2개','total':24000,'source':'Store A'},'comparisons':[{'product':'Model B','quantity':'2개','total':22000,'source':'Store B','kind':'similar','basis':'Same purpose and essential size, two physical units','differences':'브랜드와 모델이 다름.','allow_lower_price':True}]}]}
 with TemporaryDirectory()as tmp:
  root=Path(tmp);doc=root/'fixture.hwpx';spec=root/'scope.json'
  count=0
  def check(name,expected=1,scope=manifest,**kwargs):
   nonlocal count
   document(doc,**kwargs)
   args=[sys.executable,str(verifier),str(doc),'--expected-main','1','--comparisons-per-main','1']
   if scope is not None:
    spec.write_text(json.dumps(scope,ensure_ascii=False),encoding='utf-8');args+=['--equivalence-manifest',str(spec)]
   flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
   result=subprocess.run(args,capture_output=True,text=True,creationflags=flags)
   assert result.returncode==expected,(name,result.returncode,result.stdout,result.stderr)
   count+=1
  check('default rejects changed product',scope=None,total=30000)
  check('default accepts exact product',expected=0,scope=None,product='Model A',total=30000)
  check('authorized similar lower price',expected=0)
  check('actual quantity mismatch',quantity='3개')
  check('actual total mismatch',total=23000)
  check('actual product mismatch',product='Model C')
  check('actual source mismatch',source='Store C')
  check('missing visible difference',note='유사제품')
  check('missing picture',pictures=1)
  missing_auth=deepcopy(manifest);missing_auth['authorization']=''
  check('authorization missing',expected=2,scope=missing_auth)
  no_exception=deepcopy(manifest);no_exception['items'][0]['comparisons'][0].pop('allow_lower_price')
  check('lower price exception missing',scope=no_exception)
  wrong_kind=deepcopy(manifest);wrong_kind['items'][0]['comparisons'][0]['kind']='identical'
  check('similar cannot claim identical',scope=wrong_kind)
  missing_basis=deepcopy(manifest);missing_basis['items'][0]['comparisons'][0]['basis']=''
  check('common basis missing',scope=missing_basis)
  same_seller=deepcopy(manifest);same_seller['items'][0]['comparisons'][0]['source']='Store A'
  check('seller must differ',scope=same_seller,source='Store A')
  print(f'PASS: {count} behavioral cases')
if __name__=='__main__':main()
