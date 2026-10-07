"""Read saved TXT/EML bodies and verify user-selected forms of address."""
from __future__ import annotations

import argparse
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from pathlib import Path


class VisibleHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"br", "p", "div"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def read_bodies(path: Path) -> list[str]:
    if path.suffix.lower() == ".txt":
        return [path.read_text(encoding="utf-8-sig")]
    if path.suffix.lower() != ".eml":
        raise ValueError("Expected UTF-8 TXT or MIME EML")
    message = BytesParser(policy=policy.default).parsebytes(path.read_bytes())
    contents = []

    def visit(part):
        if part.get_content_disposition() == "attachment" or part.get_filename():
            return
        if part.is_multipart():
            for child in part.iter_parts():
                visit(child)
        elif part.get_content_type() in {"text/plain", "text/html"}:
            content = part.get_content()
            if part.get_content_type() == "text/html":
                parser = VisibleHTML()
                parser.feed(content)
                content = "".join(parser.parts)
            contents.append(content)

    visit(message)
    if not contents:
        raise ValueError("EML has no message body")
    return contents


def read_body(path: Path) -> str:
    return "\n".join(read_bodies(path))


def problems(text: str, required: list[str], forbidden: list[str]) -> list[str]:
    return (["Required wording missing" for value in required if value not in text]
            + ["Forbidden wording remains" for value in forbidden if value in text])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--require", action="append", required=True)
    parser.add_argument("--forbid", action="append", default=[])
    args = parser.parse_args()
    failed = False
    for path in args.files:
        try:
            issues = [issue for body in read_bodies(path)
                      for issue in problems(body, args.require, args.forbid)]
        except (OSError, UnicodeError, ValueError) as exc:
            issues = [type(exc).__name__]
        failed |= bool(issues)
        print(f"{path.name}: {'FAIL: ' + '; '.join(issues) if issues else 'PASS'}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
