#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "weasyprint",
#     "markdown",
# ]
# ///
"""Markdown to PDF converter with Korean support."""

import re
import sys

import markdown
from weasyprint import HTML

CSS = """
@page {
  size: A4;
  margin: 2.5cm;
}
body {
  font-family: "Noto Sans CJK KR", "Noto Sans KR", sans-serif;
  font-size: 10pt;
  line-height: 1.6;
  color: #333;
}
h1 {
  font-size: 20pt;
  border-bottom: 2px solid #333;
  padding-bottom: 0.3em;
  margin-top: 1.5em;
}
h2 {
  font-size: 15pt;
  border-bottom: 1px solid #ccc;
  padding-bottom: 0.2em;
  margin-top: 1.5em;
}
h3 {
  font-size: 12pt;
  margin-top: 1.2em;
}
code {
  font-family: "JetBrains Mono", "Noto Sans Mono CJK KR", monospace;
  font-size: 9pt;
  background: #f5f5f5;
  padding: 0.15em 0.3em;
  border-radius: 3px;
}
pre {
  background: #f5f5f5;
  padding: 1em;
  border-radius: 5px;
  overflow-x: hidden;
  word-wrap: break-word;
  white-space: pre-wrap;
  line-height: 1.4;
}
pre code {
  background: none;
  padding: 0;
}
table {
  border-collapse: collapse;
  width: 100%;
  table-layout: fixed;
  margin: 1em 0;
}
th, td {
  border: 1px solid #ddd;
  padding: 0.5em 0.8em;
  text-align: left;
  word-break: break-word;
  overflow-wrap: break-word;
}
th {
  background: #f5f5f5;
  font-weight: 600;
}
ul, ol {
  padding-left: 1.5em;
}
hr {
  border: none;
  border-top: 1px solid #ddd;
  margin: 2em 0;
}
"""


def strip_frontmatter(text):
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3 :].strip()
    return text


def preprocess(text):
    # 긴 box-drawing 문자(─) 축소 (PDF 오버플로우 방지)
    text = re.sub(r"─{20,}", "─" * 40, text)
    # 리스트 앞에 빈 줄이 없으면 markdown 파서가 리스트로 인식하지 못함
    text = re.sub(r"(\n[^\n-][^\n]*\n)(- )", r"\1\n\2", text)
    return text


def read_md(path):
    with open(path, "r") as f:
        text = f.read()
    return preprocess(strip_frontmatter(text))


def convert(input_paths, output_path=None):
    if isinstance(input_paths, str):
        input_paths = [input_paths]

    if output_path is None:
        output_path = input_paths[0].rsplit(".", 1)[0] + ".pdf"

    parts = []
    for path in input_paths:
        parts.append(read_md(path))
    md_text = "\n\n\\newpage\n\n".join(parts)

    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "nl2br"])
    # \newpage → CSS page break
    html_body = html_body.replace("\\newpage", '<div style="page-break-before: always;"></div>')

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    HTML(string=html).write_pdf(output_path)
    return output_path


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Markdown to PDF converter")
    parser.add_argument("inputs", nargs="+", help="Input markdown file(s)")
    parser.add_argument("-o", "--output", help="Output PDF path")
    args = parser.parse_args()

    result = convert(args.inputs, args.output)
    print(f"Done: {result}")


if __name__ == "__main__":
    main()
