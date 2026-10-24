"""Generate contract/README.md from contract/interfaces.yaml.

Usage:
    python tools/contract_readme.py          write contract/README.md
    python tools/contract_readme.py --check  exit 1 if README.md is out of date
"""

import argparse
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = ROOT / "contract" / "interfaces.yaml"
README = ROOT / "contract" / "README.md"

REQUIRED = ("topic", "type", "transport", "from", "to", "rate_hz", "max_latency_ms")
TRANSPORTS = ("ros", "can")

HEADER = """\
# Interface contract

<!-- Generated from interfaces.yaml by tools/contract_readme.py. Do not edit by hand. -->

Every topic between layers, with its rate and latency budget (proposal section 3.3).
The machine-readable source is [interfaces.yaml](interfaces.yaml); the contract test (T1.6)
reads that file. To change the contract, edit the YAML, then run `pixi run contract-readme`.
"""


def load(path=CONTRACT):
    with open(path) as f:
        return yaml.safe_load(f)


def validate(contract):
    """Return a list of problems. An empty list means the contract is valid."""
    problems = []
    topics = contract.get("topics") or []
    if not topics:
        problems.append("no topics")
    seen = set()
    for i, entry in enumerate(topics):
        name = entry.get("topic", f"entry {i}")
        for field in REQUIRED:
            if entry.get(field) in (None, ""):
                problems.append(f"{name}: missing {field}")
        if name in seen:
            problems.append(f"{name}: listed twice")
        seen.add(name)
        if entry.get("transport") not in TRANSPORTS:
            problems.append(f"{name}: transport must be one of {TRANSPORTS}")
        rate = entry.get("rate_hz")
        if isinstance(rate, list):
            if len(rate) != 2 or not all(_positive(r) for r in rate) or rate[0] > rate[1]:
                problems.append(f"{name}: rate_hz range must be [min, max], both positive")
        elif not _positive(rate):
            problems.append(f"{name}: rate_hz must be positive")
        if not _positive(entry.get("max_latency_ms")):
            problems.append(f"{name}: max_latency_ms must be positive")
    return problems


def render(contract):
    lines = [HEADER]
    lines.append("| Topic | Type | Transport | From | To | Rate (Hz) | Max latency (ms) | Notes |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for e in contract["topics"]:
        rate = e["rate_hz"]
        rate = f"{rate[0]} to {rate[1]}" if isinstance(rate, list) else str(rate)
        cells = [
            f"`{e['topic']}`",
            f"`{e['type']}`" if "/" in e["type"] else e["type"],
            e["transport"],
            e["from"],
            e["to"],
            rate,
            str(e["max_latency_ms"]),
            e.get("notes", ""),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def _positive(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if README.md is out of date")
    args = parser.parse_args()

    contract = load()
    problems = validate(contract)
    if problems:
        print("interfaces.yaml is invalid:", *problems, sep="\n  ", file=sys.stderr)
        return 1

    text = render(contract)
    if args.check:
        if not README.exists() or README.read_text() != text:
            print("contract/README.md is out of date. Run: pixi run contract-readme", file=sys.stderr)
            return 1
        print("contract/README.md is up to date.")
        return 0

    README.write_text(text)
    print(f"Wrote {README.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
