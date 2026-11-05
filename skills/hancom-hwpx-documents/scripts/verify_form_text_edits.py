#!/usr/bin/env python3
"""Fail closed when an HWPX text-only edit changes protected form structure."""
import argparse, hashlib, json, re, sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile
import xml.etree.ElementTree as ET

HP='{http://www.hancom.co.kr/hwpml/2011/paragraph}'
SECTION=re.compile(r'Contents/section[0-9]+\.xml')

def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def tree_signature(root, changed):
    parent={child:node for node in root.iter() for child in node}
    paragraphs=set(); cells=set()
    for text_node in changed:
        node=parent.get(text_node)
        while node is not None:
            if node.tag==HP+'p': paragraphs.add(node); break
            node=parent.get(node)
        if node is None: raise ValueError('changed text is not in a paragraph')
        node=parent.get(node)
        while node is not None:
            if node.tag==HP+'tc': cells.add(node); break
            node=parent.get(node)
    def sig(node):
        attrs=dict(node.attrib)
        if node in cells and 'dirty' in attrs: attrs['dirty']='CACHE_ONLY'
        children=[sig(c) for c in node if not (node in paragraphs and c.tag==HP+'linesegarray')]
        return (node.tag,tuple(sorted(attrs.items())),node.text,node.tail,tuple(children))
    return sig(root)

def verify(spec):
    source,target=spec['source'],spec['target']
    if Path(source).resolve()==Path(target).resolve(): raise ValueError('source and target must differ')
    if not isinstance(spec.get('source_sha256'),str) or not re.fullmatch(r'[0-9a-fA-F]{64}',spec['source_sha256']): raise ValueError('invalid source hash')
    if digest(source).lower()!=spec['source_sha256'].lower(): raise ValueError('source hash mismatch')
    edits=spec['edits']
    if not isinstance(edits,list) or not edits: raise ValueError('independent edit inventory required')
    bypart={}
    for e in edits:
        if (not isinstance(e,dict) or not isinstance(e.get('section'),str) or not SECTION.fullmatch(e['section'])
            or type(e.get('text_index')) is not int or e['text_index']<0
            or not isinstance(e.get('old'),str) or not isinstance(e.get('new'),str)
            or not isinstance(e.get('authorization'),str) or not e['authorization'].strip()):
            raise ValueError('invalid authorized edit inventory')
        entries=bypart.setdefault(e['section'],{})
        if e['text_index'] in entries: raise ValueError('duplicate text index')
        entries[e['text_index']]=e
    with ZipFile(source) as a,ZipFile(target) as b:
        names_a=a.namelist();names_b=b.namelist()
        if len(names_a)!=len(set(names_a)) or len(names_b)!=len(set(names_b)): raise ValueError('duplicate package entry')
        parts_a={x for x in names_a if not x.startswith('Preview/')};parts_b={x for x in names_b if not x.startswith('Preview/')}
        if parts_a!=parts_b: raise ValueError('package membership changed')
        sections={x for x in parts_a if SECTION.fullmatch(x)}
        if not set(bypart).issubset(sections): raise ValueError('edited section missing')
        for part in sorted(parts_a):
            if part not in sections:
                if a.read(part)!=b.read(part): raise ValueError('protected package part changed: '+part)
                continue
            roots=[ET.fromstring(z.read(part)) for z in (a,b)]
            nodes=[list(root.iter(HP+'t')) for root in roots]
            if len(nodes[0])!=len(nodes[1]): raise ValueError('text node structure changed: '+part)
            changed=[[],[]]
            for index,e in bypart.get(part,{}).items():
                if index>=len(nodes[0]): raise ValueError('text index out of range')
                before,after=nodes[0][index],nodes[1][index]
                if len(before) or len(after): raise ValueError('inline controls need separate review')
                if (before.text or '')!=e['old'] or (after.text or '')!=e['new']: raise ValueError('authorized text mismatch')
                before.text=after.text='AUTHORIZED_TEXT';changed[0].append(before);changed[1].append(after)
            # Existing dirty attributes must exist on both sides; only their values are cache exceptions.
            if tree_signature(roots[0],changed[0])!=tree_signature(roots[1],changed[1]):
                raise ValueError('protected structure, text, or formatting changed: '+part)
    return {'status':'PASS','scope':'structural text-only comparison; visual rendering and source authority require separate review'}

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('inventory',type=Path);args=parser.parse_args()
    try: result=verify(json.loads(args.inventory.read_text(encoding='utf-8-sig')))
    except (OSError, ValueError, KeyError, TypeError, BadZipFile, ET.ParseError) as error:
        print('FORM_TEXT_EDIT_FAILED: '+str(error),file=sys.stderr);return 1
    print(json.dumps(result));return 0
if __name__=='__main__':raise SystemExit(main())
