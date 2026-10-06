"""Exercise default rejection, authorized exceptions, and evidence-value mismatches."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile, ZIP_STORED
from xml.etree import ElementTree as E
from copy import deepcopy
import json,subprocess,sys

HP='http://www.hancom.co.kr/hwpml/2011/paragraph'
H='{'+HP+'}'
def document(path,product='Model B',quantity='2개',total=30000,source='Store B',note='유사제품: 브랜드와 모델이 다름.',pictures=2,number=1,extra_comparisons=(),split_sections=False):
 roots=[E.Element(H+'sec')]
 if split_sections:roots.append(E.Element(H+'sec'))
 texts=['Item | Model A | 수량 2개 | 총액 24,000원 | 출처 Store A',f'비교견적 {number} | Item | {product} | 수량 {quantity} | 총액 {total:,}원 | 출처 {source}',note]
 for extra in extra_comparisons:
  texts += [f"비교견적 {extra['number']} | Item | {extra['product']} | 수량 2개 | 총액 {extra['total']:,}원 | 출처 {extra['source']}",extra.get('note','')]
 for index,s in enumerate(texts):
  root=roots[1] if split_sections and index else roots[0]
  p=E.SubElement(root,H+'p');run=E.SubElement(p,H+'run');E.SubElement(run,H+'t').text=s
 for index in range(pictures):
  root=roots[1] if split_sections and index else roots[0]
  E.SubElement(E.SubElement(root,H+'pic'),H+'pos',{'treatAsChar':'1','flowWithText':'1'})
 with ZipFile(path,'w')as z:
  z.writestr('mimetype','application/hwp+zip',compress_type=ZIP_STORED)
  for index,root in enumerate(roots):z.writestr(f'Contents/section{index}.xml',E.tostring(root))
def main():
 verifier=Path(__file__).with_name('verify_quote_hwpx.py')
 manifest={'authorization':'The user explicitly allowed similar products.','items':[{'item':'Item','main':{'product':'Model A','quantity':'2개','total':24000,'source':'Store A'},'comparisons':[{'product':'Model B','quantity':'2개','total':30000,'source':'Store B','kind':'similar','basis':'Same purpose and essential size, two physical units','differences':'브랜드와 모델이 다름.'}]}]}
 with TemporaryDirectory()as tmp:
  root=Path(tmp);doc=root/'fixture.hwpx';spec=root/'scope.json'
  count=0
  def check(name,expected=1,scope=manifest,required_comparisons=1,expected_main=1,**kwargs):
   nonlocal count
   document(doc,**kwargs)
   args=[sys.executable,str(verifier),str(doc),'--expected-main',str(expected_main)]
   if required_comparisons is not None:args+=['--comparisons-per-main',str(required_comparisons)]
   if scope is not None:
    spec.write_text(json.dumps(scope,ensure_ascii=False),encoding='utf-8');args+=['--equivalence-manifest',str(spec)]
   flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
   result=subprocess.run(args,capture_output=True,text=True,creationflags=flags)
   assert result.returncode==expected,(name,result.returncode,result.stdout,result.stderr)
   count+=1
  check('default rejects changed product',scope=None,total=30000)
  check('default accepts exact product',expected=0,scope=None,product='Model A',total=30000)
  check('authorized similar higher price',expected=0)
  lower=deepcopy(manifest);lower['items'][0]['comparisons'][0].update(total=22000,allow_lower_price=True)
  check('similar permission cannot authorize lower price',scope=lower,total=22000)
  equal=deepcopy(manifest);equal['items'][0]['comparisons'][0].update(total=24000,allow_lower_price=True)
  check('similar permission cannot authorize equal price',scope=equal,total=24000)
  check('actual quantity mismatch',quantity='3개')
  check('actual total mismatch',total=31000)
  check('actual product mismatch',product='Model C')
  check('actual source mismatch',source='Store C')
  check('missing visible difference',note='유사제품')
  check('missing picture',pictures=1)
  missing_auth=deepcopy(manifest);missing_auth['authorization']=''
  check('authorization missing',expected=2,scope=missing_auth)
  lower_without_flag=deepcopy(lower);lower_without_flag['items'][0]['comparisons'][0].pop('allow_lower_price')
  check('lower price fails without obsolete flag',scope=lower_without_flag,total=22000)
  wrong_kind=deepcopy(manifest);wrong_kind['items'][0]['comparisons'][0]['kind']='identical'
  check('similar cannot claim identical',scope=wrong_kind)
  missing_basis=deepcopy(manifest);missing_basis['items'][0]['comparisons'][0]['basis']=''
  check('common basis missing',scope=missing_basis)
  same_seller=deepcopy(manifest);same_seller['items'][0]['comparisons'][0]['source']='Store A'
  check('seller must differ',scope=same_seller,source='Store A')
  second={'number':2,'product':'Model A','total':32000,'source':'Store C'}
  check('two requested comparisons cannot become one',scope=None,product='Model A',total=30000,required_comparisons=2)
  duplicate_number=deepcopy(second);duplicate_number['number']=1
  check('duplicate comparison number',scope=None,product='Model A',total=30000,pictures=3,extra_comparisons=[duplicate_number],required_comparisons=2)
  duplicate_seller=deepcopy(second);duplicate_seller['source']='Store B'
  check('duplicate comparison seller',scope=None,product='Model A',total=30000,pictures=3,extra_comparisons=[duplicate_seller],required_comparisons=2)
  check('default accepts two distinct comparisons',expected=0,scope=None,product='Model A',total=30000,pictures=3,extra_comparisons=[second],required_comparisons=None)
  check('exact comparison seller must differ',scope=None,product='Model A',total=30000,source='Store A')
  check('comparison numbering starts at one',scope=None,product='Model A',total=30000,number=2)
  check('valid comparison in later section',expected=0,scope=None,product='Model A',total=30000,split_sections=True)
  check('unrequested comparison in later section',scope=None,product='Model A',total=30000,split_sections=True,required_comparisons=0)
  two_similar=deepcopy(manifest)
  first=two_similar['items'][0]['comparisons'][0];first.update(total=30000)
  other=deepcopy(first);other.update(product='Model C',total=32000,source='Store C',differences='포장 구성이 다름.')
  two_similar['items'][0]['comparisons'].append(other)
  second_note={'number':2,'product':'Model C','total':32000,'source':'Store C','note':'유사제품: 브랜드와 모델이 다름. 포장 구성이 다름.'}
  check('difference on another comparison is insufficient',scope=two_similar,total=30000,note='유사제품',pictures=3,extra_comparisons=[second_note],required_comparisons=2)
  check('invalid request count',expected=2,scope=None,expected_main=0)
  print(f'PASS: {count} behavioral cases')
if __name__=='__main__':main()
