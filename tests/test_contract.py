"""Unit tests for the interface contract file and its README generator."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import contract_readme  # noqa: E402


def test_contract_is_valid():
    assert contract_readme.validate(contract_readme.load()) == []


def test_readme_is_up_to_date():
    expected = contract_readme.render(contract_readme.load())
    assert contract_readme.README.read_text() == expected, "run: pixi run contract-readme"


def test_validate_catches_missing_field():
    bad = {"topics": [{"topic": "/x", "type": "std_msgs/msg/Empty", "transport": "ros",
                       "from": "a", "to": "b", "rate_hz": 10}]}
    assert "/x: missing max_latency_ms" in contract_readme.validate(bad)


def test_validate_catches_bad_rate():
    bad = {"topics": [{"topic": "/x", "type": "std_msgs/msg/Empty", "transport": "ros",
                       "from": "a", "to": "b", "rate_hz": [30, 15], "max_latency_ms": 10}]}
    assert any("rate_hz range" in p for p in contract_readme.validate(bad))
