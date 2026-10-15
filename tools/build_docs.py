#!/usr/bin/env python3
"""
Build the docs as web pages and one PDF, from the markdown in docs/.

Purpose: docs that are easy to scan. Each page gets a red title bar, a short lead, its
sections as separate cards, tables and pictures, and a reading time. Markdown stays the
source: edit docs/<page>.md, then rebuild.

    pixi run docs              # docs/html/*.html, aav-docs.pdf and aav-release-notes.pdf
    pixi run docs --no-pdf     # just the web pages

Only the pages in PAGES are built, in that order. Open docs/html/index.html in a browser.

Markdown extras on top of the usual (headings, lists, tables, code):
- `!!! note "Title"` or `!!! warning "Title"`, body indented: a callout box.
- `[[works]]`, `[[untested]]`, `[[stub]]`, `[[missing]]`, `[[later]]`, `[[needs-you]]`:
  a status badge.
- `[[pages]]` alone on a line: the reading list, with reading times.
"""

import argparse
import datetime
import html
from pathlib import Path
import re
import shutil
import sys

import markdown

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / 'docs'
OUT = DOCS / 'html'
STYLE = DOCS / 'style.css'
WPM = 150          # an unhurried reading speed, so the times are a promise
READ_FIRST = 10    # PAGES[:10] are the reading list; the rest are reference

# (file in docs/, menu title, what it's for)
PAGES = [
    ('index.md', 'Start here', 'The picture, and where to go next'),
    ('overview.md', 'Overview', 'Everything in aav: ours, stock, inherited, missing'),
    ('release-notes.md', 'Release notes', 'Release 0.1: what this version does, at a glance'),
    ('first-day.md', 'Your first day', 'Install, the turtle, rqt_graph, Gazebo, Nav2'),
    ('how-it-fits.md', 'How it fits', 'What each box does, and the safety layers'),
    ('team.md', 'Starting points', 'One per team member: read, run, first tasks'),
    ('packages.md', 'Packages', 'What each package does, layer by layer'),
    ('work.md', 'Work', "The plan, what's done, what needs doing"),
    ('decisions.md', 'Decisions', 'Decided, Tentative, Proposed, and Q1–Q34'),
    ('infrastructure.md', 'Infrastructure', 'The repo, Pixi, the contracts, profiles, computers'),
    ('status.md', 'Status', "What works, what's untested, what's missing"),
    ('howto-driver.md', 'Build a driver', 'A new driver, from an empty folder to the turtle'),
    ('costmaps.md', 'Costmaps', 'How Nav2 sees obstacles; draw your first map'),
    ('perception.md', 'Perception', 'Cameras, YOLO, stop signs, lanes and radar'),
    ('older-code.md', 'Older code', "The previous teams' repos: what we have, what's missing"),
    ('ros2.md', 'ROS 2', 'Nodes, topics and tools; stock packages vs our code'),
    ('languages.md', 'Languages', 'Python, C++ and Rust: what goes where, and why'),
    ('run.md', 'Run it', 'Mac or Linux: install, build, every command'),
    ('mac.md', 'Your Mac', 'Set up the Mac, join the car, drive and watch'),
    ('simulation.md', 'Simulation', 'Gazebo, replay, CARLA, and when nothing moves'),
    ('bench.md', 'Bench mode', "The car's software on one computer, with stand-ins"),
    ('mcp.md', 'AI apps (MCP)', 'Claude and other AI apps: read the project and the graph'),
    ('firmware.md', 'Firmware', 'src vs firmware, the CAN contract, the spine'),
    ('can-plan.md', 'CAN plan', 'The KEFC CAN bus vs our CAN contract (Proposed)'),
    ('rust-firmware.md', 'Rust firmware', 'Rust on the chips: layers, frameworks, toolchains'),
    ('platforms.md', 'Platforms', 'Ubuntu, the Orin and Pis, networking'),
    ('car-photos.md', 'Car photos', 'What the car has, from photos (14 Oct), and the audit list'),
    ('conventions.md', 'Conventions', 'Names, package layout and code style'),
    ('naming.md', 'Topic areas', 'Topic names by area (Proposed), and why the EKFs meet in TF'),
    ('interfaces.md', 'Topics', 'Every topic, service, action and frame'),
    ('car_measurements.md', 'Car numbers', 'vehicle.yaml, and how to measure the car'),
    ('hud.md', 'HUD', 'The in-car screen: Rust and raylib; the Flutter app'),
    # Learn: the ideas behind the car, from zero. learn-car, learn-journey, faq and
    # glossary come first; these follow them.
    ('learn-gps.md', 'Learn: GPS', 'GNSS, RTK, NavSatFix, the datum, navsat_transform'),
    ('learn-localization.md', 'Learn: localization', 'Odometry, IMU, Kalman, frames, TF, our two EKFs'),
    ('learn-can.md', 'Learn: CAN', 'CAN from two wires to our DRIVE_CMD, byte by byte'),
]
BUILT = {name for name, _, _ in PAGES}
RELEASE = 'release-notes.md'   # also printed on its own, with a cover, to share
RELEASE_PDF = 'aav-release-notes.pdf'
# The release notes' own PDF: a running footer, and the cover on a page of its own.
RELEASE_STYLE = """
@page {
  @bottom-left { content: "AAV 2026-27 autonomy stack · release notes"; font-size: 9px;
                 color: #777; font-family: Verdana, "DejaVu Sans", Tahoma, Arial, sans-serif; }
  @bottom-center { content: none; }
  @bottom-right { content: counter(page) " of " counter(pages); font-size: 9px; color: #777;
                  font-family: Verdana, "DejaVu Sans", Tahoma, Arial, sans-serif; }
}
@page :first { @bottom-left { content: none; } @bottom-right { content: none; } }
.release .cover { break-after: page; }
"""
BADGES = ('works', 'untested', 'stub', 'missing', 'later', 'needs-you')

LIST_ITEM = re.compile(r'\s*([-*+]|\d+\.)\s')
PDF_CONTENTS_NOTE = '<p>The contents, with page numbers, are on the first page.</p>'


def slug(name):
    return name[:-3]


def minutes(text):
    prose = re.sub(r'```.*?```', '', text, flags=re.S)
    return max(1, round(len(re.findall(r"[A-Za-z0-9']+", prose)) / WPM))


def loosen(text):
    """Python-Markdown wants a blank line before a list or table; GitHub doesn't. Add it."""
    out, fence = [], False
    for line in text.splitlines():
        if line.lstrip().startswith('```'):
            fence = not fence
        prev = out[-1] if out else ''
        starts_block = LIST_ITEM.match(line) or line.startswith('|')
        prev_is_text = (prev.strip() and not prev.startswith((' ', '|', '\t'))
                        and not LIST_ITEM.match(prev))
        if not fence and starts_block and not line.startswith(' ') and prev_is_text:
            out.append('')
        out.append(line)
    return '\n'.join(out) + '\n'


def convert(text):
    md = markdown.Markdown(
        extensions=['tables', 'attr_list', 'def_list', 'md_in_html', 'sane_lists', 'toc',
                    'admonition', 'pymdownx.superfences'],
        tab_length=2)  # our lists nest by two spaces
    return md.convert(loosen(text))


def fix_links(body, pdf=False):
    """
    Point the links at the built pages.

    Links in the markdown are relative to docs/. Pages become .html; anything else points
    back at the file in the repository, one folder up from docs/html/.
    """
    def fix(m):
        attr, url = m.group(1), m.group(2)
        if re.match(r'[a-z]+:|#|/', url):
            return m.group(0)
        path, _, frag = url.partition('#')
        if path in BUILT:
            if pdf:
                return f'{attr}="#{slug(path)}{"--" + frag if frag else ""}"'
            return f'{attr}="{slug(path)}.html{"#" + frag if frag else ""}"'
        return f'{attr}="../{url}"'
    return re.sub(r'(href|src)="([^"]*)"', fix, body)


def badges(body):
    """[[works]] -> a coloured badge, everywhere except inside code."""
    parts = re.split(r'(<pre.*?</pre>|<code>.*?</code>)', body, flags=re.S)
    pattern = re.compile(r'\[\[(' + '|'.join(BADGES) + r')\]\]')
    for i in range(0, len(parts), 2):
        parts[i] = pattern.sub(
            lambda m: f'<span class="badge b-{m.group(1)}">{m.group(1).replace("-", " ")}</span>',
            parts[i])
    return ''.join(parts)


def reading_list(pages, pdf=False):
    rows = []
    for i, (name, title, purpose, mins) in enumerate(pages):
        if i == READ_FIRST:
            rows.append(f'<tr><td colspan="{5 if pdf else 4}" class="group">'
                        'Reference: look things up here</td></tr>')
        href = f'#{slug(name)}' if pdf else f'{slug(name)}.html'
        num = str(i + 1) if i < READ_FIRST else ''
        page = f'<td class="time"><a class="pg" href="{href}"></a></td>' if pdf else ''
        rows.append(f'<tr><td class="num">{num}</td>'
                    f'<td><a href="{href}"><b>{html.escape(title)}</b></a></td>'
                    f'<td>{html.escape(purpose)}</td>'
                    f'<td class="time">{mins} min</td>{page}</tr>')
    head = '<th>Page</th>' if pdf else ''
    return ('<div class="table-wrap"><table class="pages"><tr><th></th><th>Section</th>'
            f'<th>Read it for</th><th>Time</th>{head}</tr>' + ''.join(rows) + '</table></div>')


def split_page(body):
    """-> (title, intro, [(h2 id, h2 text, section html)])."""
    m = re.search(r'<h1[^>]*>(.*?)</h1>', body, flags=re.S)
    title = re.sub(r'<[^>]+>', '', m.group(1)) if m else ''
    if m:
        body = body[:m.start()] + body[m.end():]
    parts = re.split(r'(?=<h2[ >])', body)
    sections = []
    for part in parts[1:]:
        h = re.match(r'<h2(?: id="([^"]*)")?>(.*?)</h2>', part, flags=re.S)
        sections.append((h.group(1) or '', re.sub(r'<[^>]+>', '', h.group(2)), part))
    return title, parts[0].strip(), sections


def page_body(intro, sections):
    out = [f'<div class="lead">{intro}</div>'] if intro else []
    out += [f'<section class="card">{s}</section>' for _, _, s in sections]
    return '\n'.join(out)


def menu(here):
    links = []
    for i, (name, title, _) in enumerate(PAGES):
        if i == READ_FIRST:
            links.append('<span class="sep">Reference:</span>')
        cls = ' class="here"' if name == here else ''
        links.append(f'<a{cls} href="{slug(name)}.html">{html.escape(title)}</a>')
    return '\n'.join(links)


def prev_next(i):
    out = []
    if i > 0:
        name, title, _ = PAGES[i - 1]
        out.append(f'<a class="prev" href="{slug(name)}.html">'
                   f'<small>Previous</small>← {html.escape(title)}</a>')
    else:
        out.append('<span></span>')
    if i + 1 < len(PAGES):
        name, title, _ = PAGES[i + 1]
        out.append(f'<a class="next" href="{slug(name)}.html">'
                   f'<small>Next</small>{html.escape(title)} →</a>')
    return '\n'.join(out)


def web_page(i, source, title, mins, intro, sections):
    toc = ''.join(f'<a href="#{sid}">{html.escape(text)}</a>' for sid, text, _ in sections)
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · AAV 2026–27</title>
<link rel="stylesheet" href="style.css">
</head><body>
<!-- Generated from docs/{source} by tools/build_docs.py. Edit the markdown, not this file. -->
<header class="bar"><div class="kicker">AAV 2026–27 · AUTONOMY STACK</div>
<h1>{html.escape(title)}</h1>
<div class="meta">{mins} min read · {len(sections)} sections</div></header>
<nav class="menu">{menu(source)}</nav>
<main>
<nav class="toc"><span>On this page:</span>{toc}</nav>
{page_body(intro, sections)}
<nav class="prevnext">{prev_next(i)}</nav>
</main>
<footer>Source: <code>docs/{source}</code>. Edit it, then run <code>pixi run docs</code>.</footer>
</body></html>
"""


def pdf_article(name, title, intro, sections):
    """One page of the PDF: ids get the page's name in front, so they stay unique."""
    body = page_body(intro, sections)
    body = re.sub(r'id="([^"]+)"', lambda m: f'id="{slug(name)}--{m.group(1)}"', body)
    body = re.sub(r'href="#([^"]+)"', lambda m: f'href="#{slug(name)}--{m.group(1)}"', body)
    return (f'<article class="page" id="{slug(name)}"><header class="bar">'
            f'<div class="kicker">AAV 2026–27 · AUTONOMY STACK</div><h1>{html.escape(title)}</h1>'
            f'</header>{body}</article>')


def write_pdf(articles, listing, out):
    from weasyprint import HTML   # only the docs environment has it
    today = datetime.date.today().strftime('%-d %B %Y')
    cover = f"""<section class="cover"><div class="kicker">CARLETON UNIVERSITY · AAV CAPSTONE</div>
<h1>The AAV 2026–27 autonomy stack</h1>
<p class="sub">How it fits together, how to run it, and what's left</p>
{listing}
<p class="date">Built {today} from the markdown in the repository's docs/ folder</p></section>"""
    doc = (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
           f'<link rel="stylesheet" href="style.css"></head><body class="print">'
           f'{cover}{"".join(articles)}</body></html>')
    HTML(string=doc, base_url=str(OUT) + '/').write_pdf(out)


def write_release_pdf(title, intro, sections, out):
    """Print the release notes on their own: a cover with the pitch, then the sections."""
    from weasyprint import HTML   # only the docs environment has it
    inside = ''.join(f'<li><a href="#{sid}">{html.escape(text)}</a>'
                     f'<a class="pg" href="#{sid}"></a></li>' for sid, text, _ in sections)
    cover = ('<section class="cover"><div class="kicker">CARLETON UNIVERSITY · '
             f'AUTONOMOUS VEHICLE CAPSTONE</div><h1>{html.escape(title)}</h1>{intro}'
             f'<h3 class="inside-title">Inside</h3><ol class="inside">{inside}</ol></section>')
    doc = ('<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">'
           f'<link rel="stylesheet" href="style.css"><style>{RELEASE_STYLE}</style></head>'
           f'<body class="print release">{cover}{page_body("", sections)}</body></html>')
    HTML(string=doc, base_url=str(OUT) + '/').write_pdf(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--no-pdf', action='store_true', help='build the web pages only')
    args = ap.parse_args()

    OUT.mkdir(exist_ok=True)
    shutil.copyfile(STYLE, OUT / 'style.css')
    pages = []
    for name, title, purpose in PAGES:
        text = (DOCS / name).read_text(encoding='utf-8')
        pages.append((name, title, purpose, minutes(text), convert(text)))
    listing = [(n, t, p, m) for n, t, p, m, _ in pages]

    articles, release = [], None
    for i, (name, _, _, mins, body) in enumerate(pages):
        body = badges(body).replace('<table>', '<div class="table-wrap"><table>') \
                           .replace('</table>', '</table></div>')
        web = fix_links(body).replace('<p>[[pages]]</p>', reading_list(listing))
        title, intro, sections = split_page(web)
        (OUT / f'{slug(name)}.html').write_text(
            web_page(i, name, title, mins, intro, sections), encoding='utf-8')
        if not args.no_pdf:
            printed = body.replace('<p>[[pages]]</p>', PDF_CONTENTS_NOTE)
            articles.append(pdf_article(name, *split_page(fix_links(printed, pdf=True))))
            if name == RELEASE:
                release = split_page(fix_links(body, pdf=True))
    print(f'{len(pages)} pages -> {OUT.relative_to(ROOT)}/')

    if not args.no_pdf:
        pdf = OUT / 'aav-docs.pdf'
        write_pdf(articles, reading_list(listing, pdf=True), pdf)
        print(f'PDF -> {pdf.relative_to(ROOT)} ({pdf.stat().st_size // 1024} KB)')
        if release:
            pdf = OUT / RELEASE_PDF
            write_release_pdf(*release, pdf)
            print(f'PDF -> {pdf.relative_to(ROOT)} ({pdf.stat().st_size // 1024} KB)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
