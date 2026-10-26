"""
README.md lists every pixi task, so the front page shows every command (Ben, 25 Oct).

A task counts as listed when a `code` span in the README starts with its name, with or
without `pixi run` and `-e <environment>` in front.
"""

from pathlib import Path
import re
import tomllib

ROOT = Path(__file__).resolve().parents[2]


def _with_targets(table):
    """Task names in a pixi table, and in its [target.<platform>.tasks] tables."""
    names = set(table.get('tasks', {}))
    for target in table.get('target', {}).values():
        names |= set(target.get('tasks', {}))
    return names


def tasks():
    spec = tomllib.loads((ROOT / 'pixi.toml').read_text(encoding='utf-8'))
    names = _with_targets(spec)
    for feature in spec.get('feature', {}).values():
        names |= _with_targets(feature)
    return names


def listed():
    text = (ROOT / 'README.md').read_text(encoding='utf-8')
    text = re.sub(r'^```.*?^```', '', text, flags=re.S | re.M)   # the code blocks
    spans = re.findall(r'`([^`]+)`', text)
    out = set()
    for span in spans:
        words = re.sub(r'^(pixi run )?(-e [\w-]+ )?', '', span.strip()).split()
        if words:
            out.add(words[0])
    return out


def test_every_pixi_task_is_in_the_readme():
    missing = sorted(tasks() - listed())
    assert not missing, f'add these to README.md, "Every command": {missing}'
