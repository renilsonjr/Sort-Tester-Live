"""Build the player manual PDFs (#451) from manual.en.md and manual.es.md.

    python3 docs/player-manual/build_pdf.py

Writes docs/player-manual/sortquiz-manual-en.pdf and -es.pdf and copies them
to assets/manual/, where the login screen's "How to play" button opens them.

Uses only the standard library and the installed Google Chrome (headless
print to PDF). The Markdown here is a small, known subset: headings, bold,
inline code, lists, tables, block quotes, rules and image lines. That is
all this converter understands.

When a rule changes: edit both .md files, retake any screen that changed
(screens/en, screens/es: phone size 375x812, local build, test accounts only,
season bubble closed), then run this again.
"""
import html
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS = HERE.parent.parent / "assets" / "manual"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BANK = HERE.parent.parent / "backend" / "data" / "ranked" / "routes-v1.json"

# The ZIP chart (part 5) is read from the Ranked question bank itself, so the
# manual shows exactly the routes, belts and difficulty the quiz uses.
SERVICES = [("GND", "Ground", "Terrestre"), ("NDA", "Next Day Air", "Aéreo 1 día"),
            ("2DA", "2 Day Air", "Aéreo 2 días"), ("3DS", "3 Day Select", "Select 3 días")]
POINTS = {"Easy": (10, -15), "Medium": (20, -10), "Hard": (30, -5)}
LEVEL = {"en": {"Easy": "Easy", "Medium": "Medium", "Hard": "Hard"},
         "es": {"Easy": "Fácil", "Medium": "Intermedia", "Hard": "Difícil"}}
HEAD = {"en": ("State", "ZIP", "Belt", "Level", "Right", "Wrong"),
        "es": ("Estado", "ZIP", "Banda", "Nivel", "Correcta", "Incorrecta")}
MODE = {"en": {"+1": "marked +1", "EAM": "EAM", "suffix:1S": "", "suffix:2S": ""},
        "es": {"+1": "marcado +1", "EAM": "EAM", "suffix:1S": "", "suffix:2S": ""}}
BELT = {"RED": "#c0392b", "ORANGE": "#d35400", "YELLOW": "#f1c40f", "GREEN": "#2e7d32",
        "BLUE": "#2453a6", "PURPLE": "#6a2c91", "PINK": "#b03a73", "BROWN": "#6d4c2f",
        "GOLD": "#a8841f", "BLACK": "#111111"}


def _zip_key(label):
    digits = re.findall(r"\d+", label)
    return (0, int(digits[0]), label) if digits else (1, 0, label)


def zip_tables(language):
    questions = json.loads(BANK.read_text(encoding="utf-8"))["questions"]
    out = []
    for code, en_name, es_name in SERVICES:
        rows = [q for q in questions if q["context"]["service"] == code]
        rows.sort(key=lambda q: (q["context"]["mode"] != "ordinary", _zip_key(q["source"]["code_label"])))
        out.append(f"<h3>{en_name if language == 'en' else es_name}</h3>")
        head = "".join(f"<th>{h}</th>" for h in HEAD[language])
        body = []
        for q in rows:
            right, wrong = POINTS[q["difficulty"]]
            belt = q["correct_belt"]
            zip_label = q["source"]["code_label"]
            extra = MODE[language].get(q["context"]["mode"], "")
            if extra:
                zip_label = f"{zip_label} ({extra})"
            state = q["source"]["state_label"]
            state = {"*": "—", "Any state": "Any" if language == "en" else "Todos"}.get(state, state)
            ink = "#1e1a16" if belt in ("YELLOW",) else "#fff"
            body.append(
                f"<tr><td>{html.escape(state)}</td><td class='zip'>{html.escape(zip_label)}</td>"
                f"<td><span class='belt' style='background:{BELT.get(belt, '#777')};color:{ink}'>{belt}</span></td>"
                f"<td>{LEVEL[language][q['difficulty']]}</td><td class='pts'>+{right}</td><td class='pts'>−{-wrong}</td></tr>"
            )
        out.append(f"<table class='zips'><thead><tr>{head}</tr></thead><tbody>{''.join(body)}</tbody></table>")
    return "\n".join(out)


CSS = """
@page { size: Letter; margin: 14mm 14mm 16mm; }
* { box-sizing: border-box; }
body { font-family: -apple-system, "Helvetica Neue", Arial, sans-serif; color: #1e1a16;
       font-size: 11.5pt; line-height: 1.45; }
h1 { font-size: 24pt; margin: 0 0 4pt; color: #3a2410; }
h2 { font-size: 17pt; margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 2pt solid #e0a92a;
     color: #3a2410; break-after: avoid; }
h3 { font-size: 13pt; margin: 12pt 0 4pt; color: #5a3a14; break-after: avoid; }
p { margin: 5pt 0; }
ul, ol { margin: 4pt 0 6pt 18pt; padding: 0; }
li { margin: 2pt 0; }
code { background: #f3ead8; padding: 0 3pt; border-radius: 3pt; font-size: 10.5pt; }
blockquote { margin: 8pt 0; padding: 6pt 10pt; background: #fbf3e1; border-left: 4pt solid #e0a92a;
             border-radius: 4pt; }
blockquote p { margin: 0; }
hr { border: 0; margin: 4pt 0; }
table { border-collapse: collapse; margin: 6pt 0; font-size: 10.5pt; }
th, td { border: 1pt solid #d9c8a6; padding: 3pt 9pt; text-align: left; }
th { background: #f3ead8; }
.step { display: flex; gap: 16pt; align-items: flex-start; margin: 6pt 0 10pt; break-inside: avoid; }
.step .txt { flex: 1; min-width: 0; }
.shots { display: flex; gap: 10pt; flex: none; }
.shots img { height: 245pt; border-radius: 9pt; border: 1pt solid #c9b48c; }
h2 + .step, h3 + .step { margin-top: 2pt; }
.chart-page { break-before: page; }
table.zips { width: 100%; font-size: 9pt; margin: 2pt 0 10pt; }
table.zips th, table.zips td { padding: 1.5pt 6pt; }
table.zips tr { break-inside: avoid; }
table.zips td.zip { font-family: Menlo, monospace; white-space: nowrap; }
table.zips td.pts { text-align: right; font-variant-numeric: tabular-nums; }
.belt { display: inline-block; min-width: 52pt; text-align: center; padding: 0 5pt; border-radius: 8pt;
        font-weight: 700; font-size: 8pt; letter-spacing: .04em; }
.faq-q { font-weight: 700; margin-top: 9pt; break-after: avoid; }
"""


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text


def convert(markdown, language="en"):
    out, lines, i = [], markdown.splitlines(), 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1
            continue
        images = re.findall(r"!\[\]\(([^)]+)\)", line)
        if images and re.fullmatch(r"(\s*!\[\]\([^)]+\)\s*)+", line):
            tags = "".join(f'<img src="{src}" alt="">' for src in images)
            # the text this screen illustrates: the blocks since the last
            # heading or screen go on the left, the screen on the right
            text = []
            while out and not re.match(r"<(h\d|hr|div)", out[-1]):
                text.insert(0, out.pop())
            out.append(f'<div class="step"><div class="txt">{"".join(text)}</div>'
                       f'<div class="shots">{tags}</div></div>')
            i += 1
            continue
        if line == "<!-- ZIP-TABLE -->":
            out.append(zip_tables(language))
            i += 1
            continue
        if line == "<!-- NEW-PAGE -->":
            out.append('<div class="chart-page"></div>')
            i += 1
            continue
        if line == "---":
            out.append("<hr>")
            i += 1
            continue
        heading = re.match(r"(#{1,3}) (.*)", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
            i += 1
            continue
        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"-+", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, *body = rows
            table = "<tr>" + "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr>"
            for row in body:
                table += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in row) + "</tr>"
            out.append(f"<table>{table}</table>")
            continue
        if line.startswith("> "):
            out.append(f"<blockquote><p>{inline(line[2:])}</p></blockquote>")
            i += 1
            continue
        for marker, tag in ((r"- ", "ul"), (r"\d+\. ", "ol")):
            if re.match(marker, line):
                items = []
                while i < len(lines) and re.match(marker, lines[i]):
                    items.append(f"<li>{inline(re.sub('^' + marker, '', lines[i]))}</li>")
                    i += 1
                out.append(f"<{tag}>{''.join(items)}</{tag}>")
                break
        else:
            # a bold-only line followed by text is an FAQ question
            if re.fullmatch(r"\*\*[^*]+\*\*", line) and i + 1 < len(lines) and lines[i + 1].strip():
                out.append(f'<p class="faq-q">{inline(line[2:-2])}</p>')
            else:
                out.append(f"<p>{inline(line)}</p>")
            i += 1
    return "\n".join(out)


def build(language):
    source = HERE / f"manual.{language}.md"
    page = HERE / f".manual.{language}.html"
    pdf = HERE / f"sortquiz-manual-{language}.pdf"
    title = source.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
    page.write_text(
        f'<!doctype html><html lang="{language}"><head><meta charset="utf-8">'
        f"<title>{html.escape(title)}</title><style>{CSS}</style></head>"
        f"<body>{convert(source.read_text(encoding='utf-8'), language)}</body></html>",
        encoding="utf-8",
    )
    subprocess.run(
        [CHROME, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
         f"--print-to-pdf={pdf}", page.as_uri()],
        check=True, capture_output=True,
    )
    page.unlink()
    ASSETS.mkdir(parents=True, exist_ok=True)
    shutil.copy(pdf, ASSETS / pdf.name)
    return pdf


if __name__ == "__main__":
    for lang in sys.argv[1:] or ["en", "es"]:
        print(build(lang))
