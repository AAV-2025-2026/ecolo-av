"""
Every README has a CLAUDE.md beside it that reads it in (CLAUDE.md, Ben 25 Oct).

Claude Code loads a folder's CLAUDE.md when it works there; `@README.md` pulls the README
in with it, so the Elephant-Goldfish skills (and any session) see each folder's README.
"""

from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[2]


def tracked(name):
    # In git, not just on this disk: a fresh clone (CI's) must have it too.
    try:
        out = subprocess.run(['git', 'ls-files', '-z', '--', f'*{name}', name], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip('not a git checkout')
    # archive/ is the older teams' repos as they were: one CLAUDE.md at its top covers it.
    return {ROOT / p for p in out.split('\0') if p and not p.startswith('archive/')}


def readmes():
    return sorted(tracked('README.md'))


def test_every_readme_has_a_claude_md():
    claude = tracked('CLAUDE.md')
    missing = [str(r.parent.relative_to(ROOT)) for r in readmes()
               if r.parent / 'CLAUDE.md' not in claude]
    assert not missing, f'folders with a README but no CLAUDE.md: {missing}'


def test_each_claude_md_reads_its_readme():
    # The root CLAUDE.md names README.md in its first lines instead: it's long enough.
    bad = [str(r.parent.relative_to(ROOT)) for r in readmes()
           if r.parent != ROOT and (r.parent / 'CLAUDE.md').is_file()
           and '@README.md' not in (r.parent / 'CLAUDE.md').read_text(encoding='utf-8')]
    assert not bad, f'CLAUDE.md without @README.md: {bad}'
    assert 'README.md' in (ROOT / 'CLAUDE.md').read_text(encoding='utf-8')
