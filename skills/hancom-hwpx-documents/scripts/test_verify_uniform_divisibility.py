"""Synthetic uniform-cost regressions: no real records or user paths."""
import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile
from validate_hwpx_opensource import verify_form_fields
import verify_per_person_costs as costs


class UniformCostTests(unittest.TestCase):
    def setUp(self):
        self.scratch=Path(tempfile.gettempdir()).resolve()
        self.folder=Path(tempfile.mkdtemp(prefix='uniform-cost-',dir=self.scratch))
        if self.folder.resolve().parent != self.scratch: raise RuntimeError('unsafe scratch')
        self.addCleanup(self.clean)
        def field(value,unit):
            return {'value':value,'unit':unit,'provenance':'user_confirmed','source':'synthetic independent instruction'}
        self.spec={'total':field(1200,'원'),'quantity':field(3,'명'),'quantity_unit':'명',
                   'frequency':field(2,'회'),'unit_price':field(200,'원')}

    def clean(self):
        p=self.folder.resolve()
        if p.parent != self.scratch or not p.name.startswith('uniform-cost-'): raise RuntimeError('unsafe cleanup')
        shutil.rmtree(p)

    def test_source_backed_uniform_cost_passes(self):
        self.assertEqual(costs.verify_uniform_divisibility(self.spec)['status'],'PASS')

    def test_non_integer_won_is_unresolved_without_balancing_item(self):
        self.spec['total']['value']=1000
        result=costs.verify_uniform_divisibility(self.spec)
        self.assertEqual(result['reason'],'non_integer_won_unit_price')
        self.assertEqual(result['remainder'],4)
        self.assertNotIn('suggested_price',result)
        self.assertEqual(result['source_price_total'],1200)
        self.assertEqual(result['target_difference'],-200)

    def test_divisibility_does_not_prove_a_price(self):
        del self.spec['unit_price']
        self.assertEqual(costs.verify_uniform_divisibility(self.spec)['reason'],'unit_price_source_needed')

    def test_source_price_mismatch_remains_unresolved(self):
        self.spec['unit_price']['value']=199
        result=costs.verify_uniform_divisibility(self.spec)
        self.assertEqual(result['reason'],'source_unit_price_disagrees')
        self.assertEqual(result['target_difference'],6)

    def test_unverified_source_and_user_unconfirmed_proposals_fail(self):
        for key in ('total','quantity','frequency','unit_price'):
            spec=copy.deepcopy(self.spec); spec[key]['provenance']='assistant_unconfirmed'
            with self.subTest(key=key), self.assertRaises(ValueError): costs.verify_uniform_divisibility(spec)

    def test_invented_extra_item_or_adjustment_is_rejected(self):
        for extra in ('additional_item','surcharge','adjustment','extra_terms'):
            spec=copy.deepcopy(self.spec); spec[extra]={'value':3}
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError,'extra components'):
                costs.verify_uniform_divisibility(spec)

    def test_exact_saved_formula_rejects_unapproved_addend(self):
        path=self.folder/'synthetic.hwpx'
        expected='200원×3명×2회'
        inventory={'fields':[{'section':'Contents/section0.xml','table':0,'row':0,'col':0,
                              'expected':expected,'source':'independent synthetic factors'}]}
        def write(text):
            xml=('<s:sec xmlns:s="urn:synthetic" xmlns:p="http://www.hancom.co.kr/hwpml/2011/paragraph">'
                 '<p:p><p:run><p:tbl><p:tr><p:tc><p:cellAddr rowAddr="0" colAddr="0"/>'
                 '<p:subList><p:p><p:run><p:t>'+text+'</p:t></p:run></p:p></p:subList>'
                 '</p:tc></p:tr></p:tbl></p:run></p:p></s:sec>')
            with ZipFile(path,'w') as z: z.writestr('Contents/section0.xml',xml)
        write(expected)
        self.assertEqual(verify_form_fields(path,inventory)['checked_fields'],1)
        write(expected+'+5원×2개')
        with self.assertRaisesRegex(ValueError,'differs from expected'):
            verify_form_fields(path,inventory)

    def test_nonpositive_and_wrong_unit_are_rejected(self):
        for key in ('total','quantity','frequency','unit_price'):
            spec=copy.deepcopy(self.spec); spec[key]['value']=0
            with self.subTest(key=key), self.assertRaises(ValueError): costs.verify_uniform_divisibility(spec)
        self.spec['quantity']['unit']='회'; self.spec['quantity_unit']='회'
        with self.assertRaises(ValueError): costs.verify_uniform_divisibility(self.spec)

    def test_cli_returns_nonzero_for_unresolved(self):
        inventory=self.folder/'private.json'
        inventory.write_text(json.dumps(self.spec),encoding='utf-8')
        cmd=[sys.executable,str(Path(costs.__file__)),str(inventory),'--unit-divisibility-check']
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,0)
        self.spec['total']['value']=1000; inventory.write_text(json.dumps(self.spec),encoding='utf-8')
        self.assertEqual(subprocess.run(cmd,capture_output=True).returncode,1)


if __name__=='__main__': unittest.main()
