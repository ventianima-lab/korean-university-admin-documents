import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('mixed', Path(__file__).with_name('verify_mixed_lineseg.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def doc(offset, inline='<hp:lineBreak/>'):
    return f'''<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section"
        xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
        <hp:p><hp:run><hp:t>abc{inline}def</hp:t></hp:run>
        <hp:linesegarray><hp:lineseg textpos="0"/><hp:lineseg textpos="{offset}"/></hp:linesegarray></hp:p></hs:sec>'''.encode()


class MixedContentTest(unittest.TestCase):
    def test_tail_text_is_counted(self):
        self.assertEqual(module.inspect_section(doc(4))[0]['status'], 'within_full_text')

    def test_actual_overflow_fails(self):
        self.assertEqual(module.inspect_section(doc(7))[0]['status'], 'overflow')

    def test_other_inline_control_is_not_waived(self):
        inline = '<hp:lineBreak/><hp:tab/>'
        self.assertEqual(module.inspect_section(doc(4, inline))[0]['status'], 'unsupported_inline_control')


if __name__ == '__main__':
    unittest.main()
