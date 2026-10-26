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
from zipfile import ZipFile
import argparse,json,xml.etree.ElementTree as ET
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

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('hwpx',type=Path);p.add_argument('inventory',type=Path);a=p.parse_args()
    try:print(json.dumps(verify(a.hwpx,json.loads(a.inventory.read_text(encoding='utf-8')))))
    except (ValueError,KeyError) as error:p.exit(1,f'INPUT_COVERAGE_FAILED: {error}\n')
if __name__=='__main__':main()
