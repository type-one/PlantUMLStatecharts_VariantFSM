"""Regression tests for parser robustness and reentrancy."""

from pathlib import Path
import sys

import pytest

TRANSLATOR_DIR = Path(__file__).resolve().parents[1]
if str(TRANSLATOR_DIR) not in sys.path:
    sys.path.insert(0, str(TRANSLATOR_DIR))

from model import Event
from statecharts import Parser


def test_event_parse_rejects_malformed_argument_position():
    """Argument-list token must be the final token in an event sequence.

    This guards against an AttributeError regression where Event.parse tried to
    call a non-existent self.fatal() method on malformed input.
    """
    event = Event()

    with pytest.raises(ValueError, match='argument list must be the last token'):
        event.parse(['event_name', '(x)', 'unexpected_tail'])


def test_parser_translate_resets_machine_registry(repo_root: Path, tmp_path: Path):
    """Reusing one Parser instance must not leak machines between translate calls."""
    parser = Parser()

    out1 = tmp_path / 'out1'
    out2 = tmp_path / 'out2'

    parser.translate(
        str(repo_root / 'examples' / 'SimpleFSM.plantuml'),
        'hpp20',
        '',
        output_dir=str(out1),
    )
    assert sorted(parser.machines.keys()) == ['SimpleFSM']

    parser.translate(
        str(repo_root / 'examples' / 'Triggers.plantuml'),
        'hpp20',
        '',
        output_dir=str(out2),
    )
    assert sorted(parser.machines.keys()) == ['Triggers']
