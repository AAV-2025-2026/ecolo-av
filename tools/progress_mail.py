#!/usr/bin/env python3
"""Email a progress update as a red-and-white HTML page (the car's colours).

Purpose: let people follow the work from a phone. Write the update in a small markdown
subset, and this renders and sends it. Standard library only, so it runs anywhere.

    tools/progress_mail.py --subject "Builds on Linux" --file update.md
    tools/progress_mail.py --subject "..." --file update.md --attach docs/html/aav-docs.pdf
    tools/progress_mail.py --subject "..." --file update.md --dry-run --preview /tmp/u.html

The markdown subset:
- `## Section` and `### Sub-heading`
- `- ` bullets
- `| a | b |` tables (the first row is the header; skip the `|---|` line)
- `> ` a callout, for a decision or a question
- four-space indent: a command
- `**bold**`, `` `code` ``, [text](url)
Status emoji make it scannable: ✅ done, 🔧 in progress, ⚠️ needs you, 📊 numbers.

Settings come from the environment, else from ~/.config/aav/mail.env (KEY=VALUE lines,
never committed, because it holds personal addresses):
- AAV_MAIL_TO: the recipient (required)
- AAV_MAIL_FROM: the sender
- AAV_SMTP_SERVER: the relay (Carleton's on-campus relay by default)
"""

import argparse
from email.message import EmailMessage
import html
import mimetypes
import os
from pathlib import Path
import re
import smtplib
import sys

RED = '#C8102E'
DARK = '#222222'
GREY = '#F4F4F4'
CONFIG = Path.home() / '.config' / 'aav' / 'mail.env'
DEFAULT_SMTP = 'smtp-server1.carleton.ca'
SUBJECT_PREFIX = '[aav]'


def settings():
    values = {}
    if CONFIG.exists():
        for line in CONFIG.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.lstrip().startswith('#'):
                key, value = line.split('=', 1)
                values[key.strip()] = value.strip()
    values.update({k: v for k, v in os.environ.items() if k.startswith('AAV_')})
    values.setdefault('AAV_SMTP_SERVER', DEFAULT_SMTP)
    return values


def inline(text):
    """Escape, then apply **bold**, `code` and [links](url)."""
    out = html.escape(text, quote=False)
    out = re.sub(r'`([^`]+)`', r'<code style="background:#eee;padding:1px 4px;'
                 r'border-radius:3px;font-family:Menlo,Consolas,monospace">\1</code>', out)
    out = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', out)
    out = re.sub(r'\[([^\]]+)\]\(([^)\s]+)\)', rf'<a style="color:{RED}" href="\2">\1</a>', out)
    return out


def table(rows):
    cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows
             if not re.fullmatch(r'\s*\|?[\s:|-]+\|?\s*', r)]
    head, body = cells[0], cells[1:]
    th = ''.join(f'<th style="background:{RED};color:#fff;text-align:left;padding:6px 10px">'
                 f'{inline(c)}</th>' for c in head)
    trs = ''.join(
        '<tr>' + ''.join(f'<td style="padding:6px 10px;background:{GREY if i % 2 else "#fff"};'
                         f'border-bottom:1px solid #ddd">{inline(c)}</td>' for c in r) + '</tr>'
        for i, r in enumerate(body))
    return (f'<table style="border-collapse:collapse;margin:8px 0 14px;font-size:14px">'
            f'<tr>{th}</tr>{trs}</table>')


def render_body(markdown):
    """The markdown subset above -> HTML with inline styles (mail clients drop <style>)."""
    out, para, bullets, rows, code = [], [], [], [], []

    def flush():
        if para:
            out.append(f'<p style="margin:6px 0 10px">{inline(" ".join(para))}</p>')
            para.clear()
        if bullets:
            items = ''.join(f'<li style="margin:3px 0">{inline(b)}</li>' for b in bullets)
            out.append(f'<ul style="margin:4px 0 12px;padding-left:22px">{items}</ul>')
            bullets.clear()
        if rows:
            out.append(table(rows))
            rows.clear()
        if code:
            out.append(f'<pre style="background:{DARK};color:#fff;padding:10px;border-radius:6px;'
                       f'font-size:13px;overflow-x:auto">{html.escape(chr(10).join(code))}</pre>')
            code.clear()

    for line in markdown.splitlines():
        if line.startswith('    ') and not bullets:
            if para or rows:
                flush()
            code.append(line[4:])
            continue
        if code:
            flush()
        s = line.strip()
        if not s:
            flush()
        elif s.startswith('### '):
            flush()
            out.append(f'<h3 style="color:{DARK};margin:14px 0 4px;font-size:16px">{inline(s[4:])}</h3>')
        elif s.startswith('## '):
            flush()
            out.append(f'<h2 style="color:{RED};margin:20px 0 6px;font-size:19px;'
                       f'border-bottom:2px solid {RED};padding-bottom:3px">{inline(s[3:])}</h2>')
        elif s.startswith('|'):
            if para or bullets:
                flush()
            rows.append(s)
        elif s.startswith('- '):
            if para or rows:
                flush()
            bullets.append(s[2:])
        elif s.startswith('> '):
            flush()
            out.append(f'<div style="border-left:5px solid {RED};background:#FDECEE;padding:8px 12px;'
                       f'margin:8px 0 12px">{inline(s[2:])}</div>')
        elif bullets and line.startswith('  '):
            bullets[-1] += ' ' + s          # a wrapped bullet
        else:
            if bullets or rows:
                flush()
            para.append(s)
    flush()
    return '\n'.join(out)


def render(subject, markdown, greeting='Hello Ben'):
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#fff;font-family:Arial,Helvetica,sans-serif;color:{DARK};
font-size:15px;line-height:1.45">
<div style="background:{RED};color:#fff;padding:14px 18px">
<div style="font-size:12px;letter-spacing:2px;opacity:.9">AAV 2026–27 · AUTONOMY STACK</div>
<div style="font-size:21px;font-weight:bold;margin-top:4px">{html.escape(subject)}</div></div>
<div style="padding:12px 18px;max-width:760px">
<p style="font-size:16px;margin:10px 0">{html.escape(greeting)} 👋</p>
{render_body(markdown)}
<p style="color:#888;font-size:12px;margin-top:24px;border-top:1px solid #eee;padding-top:8px">
Sent by a Claude Code session working in the AAV repository on oirp-spss.</p>
</div></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--subject', required=True)
    ap.add_argument('--file', required=True, help='markdown-subset body')
    ap.add_argument('--dry-run', action='store_true', help='render only, send nothing')
    ap.add_argument('--preview', help='also write the HTML here')
    ap.add_argument('--attach', action='append', default=[], metavar='FILE',
                    help='attach a file (repeatable), e.g. the docs PDF')
    args = ap.parse_args()

    body_md = Path(args.file).read_text(encoding='utf-8')
    page = render(args.subject, body_md)
    if args.preview:
        Path(args.preview).write_text(page, encoding='utf-8')
    if args.dry_run:
        print('dry run: nothing sent' + (f'; preview in {args.preview}' if args.preview else ''))
        return 0

    cfg = settings()
    to = cfg.get('AAV_MAIL_TO')
    if not to:
        sys.exit(f'AAV_MAIL_TO is not set (environment or {CONFIG})')
    msg = EmailMessage()
    msg['Subject'] = f'{SUBJECT_PREFIX} {args.subject}'
    msg['From'] = cfg.get('AAV_MAIL_FROM', to)
    msg['To'] = to
    msg.set_content(f'{args.subject}\n\n{body_md}')
    msg.add_alternative(page, subtype='html')
    for name in args.attach:
        path = Path(name)
        kind = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        maintype, subtype = kind.split('/', 1)
        msg.add_attachment(path.read_bytes(), maintype=maintype, subtype=subtype,
                           filename=path.name)
    with smtplib.SMTP(cfg['AAV_SMTP_SERVER'], 25, timeout=30) as smtp:
        smtp.send_message(msg)
    print(f'sent to {to} via {cfg["AAV_SMTP_SERVER"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
