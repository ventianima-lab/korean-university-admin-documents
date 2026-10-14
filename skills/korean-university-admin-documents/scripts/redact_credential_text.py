"""Narrow paired ID/PW line redaction for structured notice evidence."""

import re
import unittest


PAIR = re.compile(r"(?im)(\bID[ \t]*/[ \t]*(?:PW|PASSWORD)[ \t]*[:=：])(?![ \t]*\[REDACTED\][ \t]*$)[ \t]*[^\r\n]+")


def redact_data(value):
    if isinstance(value, str):
        return PAIR.sub(r"\1 [REDACTED]", value)
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_data(item) for key, item in value.items()}
    return value


class RedactionTests(unittest.TestCase):
    def test_pair_and_next_line(self):
        import json
        source = {"body": "ID/PW : SAMPLE_ACCOUNT / SAMPLE_CREDENTIAL (shared)\nNext section", "items": [True, None, 5]}
        safe = redact_data(source)
        self.assertEqual(safe["body"], "ID/PW : [REDACTED]\nNext section")
        self.assertEqual(safe["items"], source["items"])
        self.assertEqual(json.loads(json.dumps(safe)), safe)
        self.assertEqual(redact_data(safe), safe)


if __name__ == "__main__":
    unittest.main()
