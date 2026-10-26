"""Synthetic coverage cases for text following HWPX inline controls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import unittest
from verify_input_coverage import verify


class InlineTextChecks(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'sample.hwpx'
    def package(self, text):
        xml=('<sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">'
             '<hp:p><hp:run><hp:tbl><hp:tr><hp:tc><hp:cellAddr rowAddr="0" colAddr="0"/>'
             '<hp:subList><hp:p><hp:run><hp:t>'+text+'</hp:t></hp:run></hp:p></hp:subList>'
             '</hp:tc></hp:tr></hp:tbl></hp:run></hp:p></sec>')
        with ZipFile(self.path,'w') as z:z.writestr('Contents/section0.xml',xml)
    def item(self, **values):
        return {'section':'Contents/section0.xml','table':0,'row':0,'col':0,**values}
    def test_header_after_fullwidth_space_is_not_an_empty_input(self):
        self.package('<hp:fwSpace/>Name')
        self.assertEqual(verify(self.path,{'cells':[]})['blank_cells'],0)
    def test_known_value_in_linebreak_tail_is_compared(self):
        self.package('first<hp:lineBreak/>second')
        item=self.item(status='known',reason='Supported synthetic field',source='Synthetic master',expected='firstsecond')
        self.assertEqual(verify(self.path,{'cells':[item]})['inventoried_cells'],1)
        item['expected']='first'
        with self.assertRaises(ValueError):verify(self.path,{'cells':[item]})
    def test_controlled_field_with_tail_text_is_not_blank(self):
        self.package('<hp:fwSpace/>unexpected')
        item=self.item(status='controlled',reason='Recipient input remains empty')
        with self.assertRaises(ValueError):verify(self.path,{'cells':[item]})
    def test_truly_empty_input_still_needs_a_disposition(self):
        self.package('<hp:fwSpace/>')
        with self.assertRaises(ValueError):verify(self.path,{'cells':[]})
        item=self.item(status='controlled',reason='Recipient enters after the event')
        self.assertEqual(verify(self.path,{'cells':[item]})['blank_cells'],1)


if __name__=='__main__':unittest.main()
