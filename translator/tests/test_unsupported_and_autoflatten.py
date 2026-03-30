import tempfile
from pathlib import Path

import pytest


@pytest.mark.parametrize('source_name', [
    'ComplexComposite.plantuml',
    'Pompe.plantuml',
    'SimpleOrthogonal.plantuml',
])
@pytest.mark.parametrize('mode', ['cpp', 'cpp20'])
def test_unsupported_diagrams_fail_fast(run_translator, source_name, mode):
    composite_sources = {'ComplexComposite.plantuml', 'Pompe.plantuml'}

    with tempfile.TemporaryDirectory(prefix='fsm_reg_unsupported_') as out:
        out_path = Path(out)
        result = run_translator(
            [f'examples/{source_name}', mode, '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

    output = (result.stdout or '') + (result.stderr or '')
    assert result.returncode != 0
    assert 'Unsupported PlantUML diagram features detected:' in output
    if source_name in composite_sources:
        assert '--auto-flatten' in output


def test_auto_flatten_option_behavior(run_translator):
    with tempfile.TemporaryDirectory(prefix='fsm_reg_autoflat_') as out:
        out_path = Path(out)

        ok = run_translator(
            ['examples/SimpleComposite.plantuml', 'cpp20', '--auto-flatten', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert ok.returncode == 0

        nested_ok = run_translator(
            ['examples/ComplexComposite.plantuml', 'cpp', '--auto-flatten', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert nested_ok.returncode == 0

        pompe_ok = run_translator(
            ['examples/Pompe.plantuml', 'cpp', '--auto-flatten', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert pompe_ok.returncode == 0

        pompe_hpp = (out_path / 'pompe.hpp').read_text()
        pompe_cpp = (out_path / 'pompe.cpp').read_text()
        assert 'MOCKABLE void on_activity_default_id();' in pompe_hpp
        assert 'MOCKABLE void pompe::on_activity_default_id()' in pompe_cpp

        ko = run_translator(
            ['examples/SimpleOrthogonal.plantuml', 'cpp', '--auto-flatten', '-o', str(out_path)],
            capture_output=True,
            text=True,
            check=False,
        )

    output = (ko.stdout or '') + (ko.stderr or '')
    assert ko.returncode != 0
    assert 'Auto-flatten currently does not support orthogonal/concurrent regions' in output
