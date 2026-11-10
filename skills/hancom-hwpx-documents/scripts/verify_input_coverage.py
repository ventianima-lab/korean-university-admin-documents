#!/usr/bin/env python3
"""Require an explained disposition for every saved empty table cell.

Private inventory: {"cells": [{"section": "Contents/section0.xml",
"table": 0, "row": 0, "col": 1, "status": "known|unconfirmed|controlled|unused|layout",
"reason": "...", "expected": "...", "source": "...", "lookups": ["..."]}]}.
Known cells need nonempty expected/source; unconfirmed inputs need two distinct
actually checked sources. Other statuses need a specific reason. Containers with
nested tables or pictures are excluded. This proves coverage, not source authority
or correct human classification; review the inventory independently.
"""
from pathlib import Path
from zipfile import BadZipFile,ZipFile
import argparse,json,hashlib,re,xml.etree.ElementTree as ET
NS={'hp':'http://www.hancom.co.kr/hwpml/2011/paragraph'}

def verify(path, inventory):
    listed={}
    for item in inventory.get('cells',[]):
        key=(item['section'],item['table'],item['row'],item['col'])
        if key in listed:raise ValueError('Duplicate cell disposition')
        status=item.get('status')
        if status not in {'known','unconfirmed','controlled','unused','layout'}:
            raise ValueError('Invalid disposition')
        if not item.get('reason','').strip():raise ValueError('Missing reason')
        if status=='known' and (not item.get('expected','').strip() or not item.get('source','').strip()):
            raise ValueError('Known input needs independent value/source')
        if status=='unconfirmed' and len(set(x.strip() for x in item.get('lookups',[]) if x.strip()))<2:
            raise ValueError('Unconfirmed input needs distinct checked sources')
        listed[key]=item
    found=set(); blanks=0
    with ZipFile(path) as z:
        for section in sorted(n for n in z.namelist() if n.startswith('Contents/section') and n.endswith('.xml')):
            root=ET.fromstring(z.read(section))
            for ti,table in enumerate(root.findall('.//hp:tbl',NS)):
                for tr in table.findall('hp:tr',NS):
                    for cell in tr.findall('hp:tc',NS):
                        if cell.find('.//hp:tbl',NS) is not None or cell.find('.//hp:pic',NS) is not None:continue
                        a=cell.find('hp:cellAddr',NS)
                        key=(section,ti,int(a.get('rowAddr')),int(a.get('colAddr')))
                        value=''.join(''.join(t.itertext()) for t in cell.findall('.//hp:t',NS))
                        if not value.strip():
                            blanks+=1
                            if key not in listed:raise ValueError(f'Unclassified empty cell: {key}')
                        if key in listed:
                            found.add(key);item=listed[key]
                            if item['status']=='known':
                                if value!=item['expected']:raise ValueError(f'Known value mismatch: {key}')
                            elif value.strip():raise ValueError(f'Intentionally blank input contains text: {key}')
    if found!=set(listed):raise ValueError('Inventory contains absent or non-input cells')
    return {'status':'PASS','blank_cells':blanks,'inventoried_cells':len(found)}

def verify_identity_assets(source, output, assets):
    """Byte preservation only; roles/recognition come from pre-edit source inventory."""
    if not isinstance(assets, list) or not assets:
        raise ValueError('Identity asset inventory must not be empty')
    seen_source, seen_target = set(), set()
    with ZipFile(source) as original, ZipFile(output) as candidate:
        for item in assets:
            src, dst = item['source_member'], item['target_member']
            if src in seen_source or dst in seen_target:
                raise ValueError('Duplicate identity asset mapping')
            seen_source.add(src); seen_target.add(dst)
            if not item.get('role', '').strip() or item.get('recognition') not in {'recognized', 'unresolved'}:
                raise ValueError('Identity asset role/recognition missing')
            try:
                before, after = original.read(src), candidate.read(dst)
            except KeyError as error:
                raise ValueError('Source identity asset missing in package') from error
            if hashlib.sha256(before).hexdigest() != item.get('sha256') or before != after:
                raise ValueError('Identity asset not preserved')
    return len(assets)


def verify_template_inventory(path, inventory):
    """Map an independently selected template cell range to exact saved inputs.

    Scope defines source rows and input columns before output review. Every actual
    source cell in that scope must have one mapping. Hashes and coordinates are
    checked, but the human must establish source authority, scope completeness,
    evidence meaning, identity and whether a planned value is not an outcome.
    """
    import hashlib, re
    if not isinstance(inventory, dict): raise ValueError('Inventory must be an object')
    template=inventory.get('template');scope=inventory.get('scope');fields=inventory.get('fields')
    if not isinstance(template,dict) or not isinstance(scope,list) or not scope or not isinstance(fields,list):
        raise ValueError('Template, scope and fields are required')
    source=Path(template['path'])
    if source.resolve()==Path(path).resolve(): raise ValueError('Template and output must differ')
    expected_hash=template.get('sha256')
    if not isinstance(expected_hash,str) or not re.fullmatch(r'[a-fA-F0-9]{64}',expected_hash): raise ValueError('Invalid template hash')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected_hash.lower(): raise ValueError('Template hash mismatch')
    if 'identity_assets' in inventory:
        verify_identity_assets(source, path, inventory['identity_assets'])
    target_hash=hashlib.sha256(Path(path).read_bytes()).hexdigest();evidence_hashes={}
    section=template.get('section');table_index=template.get('table')
    if not isinstance(section,str) or not re.fullmatch(r'Contents/section[0-9]+\.xml',section) or type(table_index) is not int or table_index<0:
        raise ValueError('Invalid template location')
    def read_table(package,part,index):
        if not isinstance(part,str) or not re.fullmatch(r'Contents/section[0-9]+\.xml',part) or type(index) is not int or index<0: raise ValueError('Invalid section or table')
        root=ET.fromstring(package.read(part));tables=root.findall('.//hp:tbl',NS)
        if index>=len(tables):raise ValueError('Table missing')
        result={}
        for cell in tables[index].findall('./hp:tr/hp:tc',NS):
            a=cell.find('hp:cellAddr',NS)
            if a is None:raise ValueError('Cell address missing')
            key=(int(a.get('rowAddr')),int(a.get('colAddr')))
            if key in result:raise ValueError('Duplicate cell coordinates')
            if cell.find('.//hp:tbl',NS) is not None or cell.find('.//hp:pic',NS) is not None:
                result[key]=None
            else:result[key]=''.join(''.join(t.itertext()) for t in cell.findall('.//hp:t',NS))
        return result
    def required_text(v): return isinstance(v,str) and bool(v.strip())
    def verify_evidence(evidence):
        if not isinstance(evidence,list) or not evidence:raise ValueError('Independent evidence is required')
        for item in evidence:
            if not isinstance(item,dict):raise ValueError('Invalid evidence')
            if item.get('kind')=='document':
                h=item.get('sha256');p=item.get('path');loc=item.get('location')
                if not required_text(p) or not required_text(loc) or not isinstance(h,str) or not re.fullmatch(r'[a-fA-F0-9]{64}',h): raise ValueError('Document evidence needs path, hash and location')
                if Path(p).resolve()==Path(path).resolve():raise ValueError('Output cannot serve as its own independent evidence')
                if hashlib.sha256(Path(p).read_bytes()).hexdigest()!=h.lower():raise ValueError('Document evidence hash mismatch')
                evidence_hashes[Path(p).resolve()]=h.lower()
            elif item.get('kind')=='user_instruction':
                if not required_text(item.get('reference')) or not required_text(item.get('quote')):raise ValueError('Instruction needs reference and quote')
            else:raise ValueError('Invalid evidence kind')
    with ZipFile(source) as src, ZipFile(path) as out:
        source_cells=read_table(src,section,table_index); selected=set()
        for rule in scope:
            if not isinstance(rule,dict) or type(rule.get('row_start')) is not int or type(rule.get('row_end')) is not int or rule['row_start']<0 or rule['row_end']<rule['row_start']:
                raise ValueError('Invalid scope row range')
            cols=rule.get('input_cols')
            if not isinstance(cols,list) or not cols or any(type(c) is not int or c<0 for c in cols) or len(set(cols))!=len(cols):raise ValueError('Invalid scope input columns')
            for row in range(rule['row_start'],rule['row_end']+1):
                found={(row,col) for col in cols if (row,col) in source_cells}
                if not found:raise ValueError('Scoped template row has no input cell')
                if selected & found:raise ValueError('Overlapping source scope')
                selected |= found
        mapped=set();destinations=set();cache={}
        for field in fields:
            if not isinstance(field,dict) or not isinstance(field.get('source'),dict) or not isinstance(field.get('target'),dict):raise ValueError('Invalid field mapping')
            origin=field['source'];target=field['target'];row,col=origin.get('row'),origin.get('col')
            if type(row) is not int or type(col) is not int or (row,col) not in selected or (row,col) in mapped:raise ValueError('Unscoped or duplicate source input')
            mapped.add((row,col));label_col=origin.get('label_col');label_row=origin.get('label_row',row)
            if type(label_col) is not int or type(label_row) is not int or not required_text(origin.get('label')) or source_cells.get((label_row,label_col)) is None or source_cells[(label_row,label_col)].strip()!=origin['label'].strip():raise ValueError('Source label mismatch')
            if source_cells[(row,col)] is None:raise ValueError('Complex source field requires separate review')
            dest=(target.get('section'),target.get('table'),target.get('row'),target.get('col'))
            if not isinstance(dest[0],str) or any(type(n) is not int or n<0 for n in dest[1:]) or dest in destinations:raise ValueError('Invalid or duplicate target input')
            destinations.add(dest);tk=dest[:2]
            if tk not in cache:cache[tk]=read_table(out,*tk)
            target_cells=cache[tk];actual=target_cells.get(dest[2:])
            if actual is None:raise ValueError('Target cell missing or complex')
            lr=target.get('label_row',dest[2]);lc=target.get('label_col')
            if type(lr) is not int or type(lc) is not int or not required_text(target.get('label')) or target_cells.get((lr,lc)) is None or target_cells[(lr,lc)].strip()!=target['label'].strip():raise ValueError('Target label mismatch')
            status=field.get('status');reason=field.get('reason')
            if not required_text(reason) or status not in {'known','preserved','controlled','unconfirmed','unused'}:raise ValueError('Disposition and reason required')
            if status in {'known','preserved'}:
                if field.get('value_kind') not in {'plan','fact','actual','user_preserved'}:raise ValueError('Value kind must distinguish plans, facts and actuals')
                expected=field.get('expected')
                if not required_text(expected):raise ValueError('Expected value required')
                verify_evidence(field.get('evidence'))
                if actual.strip()!=expected.strip():raise ValueError('Known or preserved field mismatch at '+str(dest))
            else:
                if actual.strip():raise ValueError('Controlled, unconfirmed or unused field not blank')
                if status=='unconfirmed':
                    lookups=field.get('lookups')
                    if not isinstance(lookups,list) or len({v.strip() for v in lookups if required_text(v)})<2:raise ValueError('Unconfirmed needs two checked sources')
        if mapped!=selected:raise ValueError('Template input omitted from inventory')
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=target_hash:raise ValueError('Output changed during verification')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected_hash.lower():raise ValueError('Template changed during verification')
    for evidence_path,expected in evidence_hashes.items():
        if hashlib.sha256(evidence_path.read_bytes()).hexdigest()!=expected:raise ValueError('Evidence changed during verification')
    return {'status':'PASS','scoped_template_fields':len(selected),'mapped_fields':len(mapped),'target_fields':len(destinations),'target_sha256':target_hash,'scope':'Selected source cells only; authority, complete scope, evidence meaning and render require independent review'}


TOTAL_LABELS = {'계', '합계', '총계'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table_cells(path, spec):
    section, index = spec.get('section'), spec.get('table')
    if not isinstance(section, str) or not re.fullmatch(r'Contents/section[0-9]+\.xml', section) or type(index) is not int or index < 0:
        raise ValueError('Invalid section or table')
    with ZipFile(path) as z:
        tables = ET.fromstring(z.read(section)).findall('.//hp:tbl', NS)
        if index >= len(tables):
            raise ValueError('Table missing')
        result = {}
        for cell in tables[index].findall('./hp:tr/hp:tc', NS):
            addr, span = cell.find('hp:cellAddr', NS), cell.find('hp:cellSpan', NS)
            if addr is None or span is None:
                raise ValueError('Cell address or span missing')
            key = (int(addr.attrib['rowAddr']), int(addr.attrib['colAddr']))
            if key in result:
                raise ValueError('Duplicate cell address')
            if cell.find('.//hp:tbl', NS) is not None or cell.find('.//hp:pic', NS) is not None:
                raise ValueError('Complex cell requires separate review')
            text = ''.join(''.join(t.itertext()) for t in cell.findall('.//hp:t', NS))
            result[key] = (''.join(text.split()), (int(span.attrib['rowSpan']), int(span.attrib['colSpan'])))
        return result


def verify_total_labels(output, data):
    source_spec, output_spec, mappings = data['source'], data['output'], data['mappings']
    source = Path(source_spec['path'])
    output = Path(output)
    if source.resolve() == output.resolve():
        raise ValueError('Source and output must differ')
    expected_hash = source_spec.get('sha256', '')
    if not re.fullmatch(r'[a-fA-F0-9]{64}', expected_hash) or digest(source) != expected_hash.lower():
        raise ValueError('Source hash mismatch')
    output_hash = digest(output)
    src, dst = table_cells(source, source_spec), table_cells(output, output_spec)
    totals = {k for k, v in src.items() if v[0] in TOTAL_LABELS}
    if not totals:
        raise ValueError('No total labels found in selected source table; review scope')
    seen_source, seen_target = set(), set()
    if not isinstance(mappings, list):
        raise ValueError('Mappings must be a list')
    for mapping in mappings:
        coords = []
        for field in ('source', 'target'):
            pos = mapping.get(field)
            if not isinstance(pos, list) or len(pos) != 2 or any(type(n) is not int or n < 0 for n in pos):
                raise ValueError('Invalid mapping coordinate')
            coords.append(tuple(pos))
        origin, target = coords
        if origin not in totals or origin in seen_source or target in seen_target:
            raise ValueError('Unselected or duplicate total mapping')
        seen_source.add(origin)
        seen_target.add(target)
        if dst.get(target) != src[origin]:
            raise ValueError(f'Total label or merged-cell span mismatch: {origin} -> {target}')
    if seen_source != totals:
        raise ValueError(f'Unmapped source total labels: {sorted(totals - seen_source)}')
    if digest(source) != expected_hash.lower() or digest(output) != output_hash:
        raise ValueError('File changed during verification')
    return {'status': 'PASS', 'total_cells': len(totals), 'output_sha256': output_hash,
            'scope': 'Selected table and mapped total labels only; review mapping, amounts and render independently'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('hwpx',type=Path);p.add_argument('inventory',type=Path);p.add_argument('--template-inventory',action='store_true',help='compare a selected source-form input scope to an independently sourced saved-field inventory');p.add_argument('--total-labels',action='store_true',help='verify mapped fixed total labels in a selected source table');a=p.parse_args()
    try:
        data=json.loads(a.inventory.read_text(encoding='utf-8-sig'))
        if a.template_inventory and a.total_labels: raise ValueError('Choose one verification mode')
        result=verify_total_labels(a.hwpx,data) if a.total_labels else verify_template_inventory(a.hwpx,data) if a.template_inventory else verify(a.hwpx,data)
        print(json.dumps(result))
    except (ValueError,KeyError,OSError,BadZipFile,ET.ParseError) as error:p.exit(1,f'INPUT_COVERAGE_FAILED: {error}\n')
if __name__=='__main__':main()
