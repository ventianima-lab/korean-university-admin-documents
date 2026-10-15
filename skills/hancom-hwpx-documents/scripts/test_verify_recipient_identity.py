import importlib.util
from io import BytesIO
from pathlib import Path
from email.message import EmailMessage
import tempfile
import unittest
from zipfile import ZipFile

spec = importlib.util.spec_from_file_location('identity', Path(__file__).with_name('verify_recipient_identity.py'))
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


def hwpx(name='가나래', stale='', split=False):
    stream = BytesIO()
    text = '<hp:t>가</hp:t><hp:t>나래</hp:t>' if split else f'<hp:t>{name}</hp:t>'
    with ZipFile(stream, 'w') as z:
        z.writestr('Contents/section0.xml', '<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:p>'+text+'</hp:p></hp:sec>')
        z.writestr('Preview/PrvText.txt', stale or name)
    return stream.getvalue()


class IdentityChecks(unittest.TestCase):
    def test_split_run_name(self):
        identity.check_hwpx(hwpx(split=True), '가나래', ['가나리'], 'fixture')

    def test_stale_preview(self):
        with self.assertRaises(ValueError):
            identity.check_hwpx(hwpx(stale='가나리'), '가나래', ['가나리'], 'fixture')

    def test_missing_confirmed_name(self):
        with self.assertRaises(ValueError):
            identity.check_hwpx(hwpx(name='가나리'), '가나래', ['가나리'], 'fixture')

    def test_correct_field_does_not_hide_wrong_signature(self):
        with self.assertRaises(ValueError):
            identity.check_hwpx(hwpx(name='가나래 작성자 가나리'), '가나래', ['가나리'], 'fixture')

    def mail(self, attachment, html='가나래 선생님'):
        message = EmailMessage()
        message.set_content('가나래 선생님')
        message.add_alternative(html, subtype='html')
        message.add_attachment(attachment, maintype='application', subtype='octet-stream', filename='form.hwpx')
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'draft.eml'
            path.write_bytes(message.as_bytes())
            return identity.verify(path, '가나래', ['가나리'])

    def test_all_mime_bodies_and_attachment_pass(self):
        result = self.mail(hwpx(), '<p>가<span>나래</span> 선생님</p>')
        self.assertEqual(result['text_bodies_checked'], 2)
        self.assertEqual(result['hwpx_attachments_checked'], 1)

    def test_stale_attachment_fails_correct_body(self):
        with self.assertRaises(ValueError):
            self.mail(hwpx(name='가나리'))

    def test_stale_html_fails_correct_plain(self):
        with self.assertRaises(ValueError):
            self.mail(hwpx(), '가나리 선생님')

    def test_stale_filename(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'가나리.txt'
            path.write_text('가나래 선생님', encoding='utf-8')
            with self.assertRaises(ValueError):
                identity.verify(path, '가나래', ['가나리'])


if __name__ == '__main__':
    unittest.main()
