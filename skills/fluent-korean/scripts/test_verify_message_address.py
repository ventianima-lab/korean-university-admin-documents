"""Synthetic regression checks for decoded message-address verification."""
import tempfile
import unittest
from email.message import EmailMessage
from pathlib import Path

from verify_message_address import problems, read_body, read_bodies


class AddressTests(unittest.TestCase):
    def test_corrected_txt_preserves_role(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "message.txt"
            path.write_text("안녕하세요, 선생님.\n특강 강사 이력서를 요청드립니다.", encoding="utf-8-sig")
            body = read_body(path)
            self.assertEqual(problems(body, ["선생님"], ["강사님"]), [])
            self.assertIn("특강 강사 이력서", body)

    def test_encoded_eml_detects_stale_address(self):
        for encoding in ("base64", "quoted-printable"):
            with self.subTest(encoding=encoding), tempfile.TemporaryDirectory() as folder:
                message = EmailMessage()
                message.set_content("안녕하세요, 강사님.", cte=encoding)
                path = Path(folder) / "message.eml"
                path.write_bytes(message.as_bytes())
                self.assertEqual(len(problems(read_body(path), ["선생님"], ["강사님"])), 2)

    def test_attachment_does_not_satisfy_body_check(self):
        with tempfile.TemporaryDirectory() as folder:
            message = EmailMessage()
            message.set_content("서류를 요청드립니다.")
            message.add_attachment("선생님", subtype="plain", filename="form.txt")
            path = Path(folder) / "message.eml"
            path.write_bytes(message.as_bytes())
            self.assertEqual(problems(read_body(path), ["선생님"], []), ["Required wording missing"])

    def test_attachment_does_not_trigger_false_positive(self):
        with tempfile.TemporaryDirectory() as folder:
            message = EmailMessage()
            message.set_content("안녕하세요, 선생님.")
            message.add_attachment("강사님", subtype="plain", filename="form.txt")
            path = Path(folder) / "message.eml"
            path.write_bytes(message.as_bytes())
            self.assertEqual(problems(read_body(path), ["선생님"], ["강사님"]), [])

    def test_html_checks_visible_text_only(self):
        with tempfile.TemporaryDirectory() as folder:
            message = EmailMessage()
            message.set_content("<style>.강사님{}</style><p>안녕하세요, 선생님.</p>", subtype="html")
            path = Path(folder) / "message.eml"
            path.write_bytes(message.as_bytes())
            self.assertEqual(problems(read_body(path), ["선생님"], ["강사님"]), [])

    def test_stale_html_alternative_cannot_hide_behind_plain_text(self):
        with tempfile.TemporaryDirectory() as folder:
            message = EmailMessage()
            message.set_content("안녕하세요, 선생님.")
            message.add_alternative("<p>안녕하세요, 강사님.</p>", subtype="html")
            path = Path(folder) / "message.eml"
            path.write_bytes(message.as_bytes())
            checks = [problems(body, ["선생님"], ["강사님"]) for body in read_bodies(path)]
            self.assertEqual(checks[0], [])
            self.assertEqual(len(checks[1]), 2)


if __name__ == "__main__":
    unittest.main()
