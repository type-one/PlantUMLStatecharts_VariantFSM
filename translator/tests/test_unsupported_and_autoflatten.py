"""
Error-path and auto-flatten behaviour tests.

These tests cover two orthogonal concerns:

1. **Fast-fail for unsupported diagrams** — the translator must reject
   PlantUML features it cannot handle (composite states, orthogonal regions)
   with a non-zero exit code and an informative error message, regardless of
   whether the user requested C++11 or C++20 output.

2. **``--auto-flatten`` flag** — when this flag is set, composite states may
   be silently collapsed into flat FSMs so that generation can proceed;
   orthogonal (concurrent) regions remain unsupported even with the flag and
   must still fail with a dedicated error message.
"""

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
    """The translator must exit non-zero and print an error for diagrams that
    use unsupported PlantUML features.

    Parametrized over:
    * ``source_name`` — three diagrams that each trigger a different unsupported
      path: ``ComplexComposite`` (deep nesting), ``Pompe`` (shallow composite
      with entry actions), ``SimpleOrthogonal`` (concurrent regions).
    * ``mode`` — both ``cpp`` (C++11) and ``cpp20`` (C++20 variant backend),
      because the guard must fire before any backend-specific code runs.

    Expectations for all 6 combinations:
    * Return-code is non-zero.
    * Combined stdout+stderr contains the string
      ``"Unsupported PlantUML diagram features detected:"``, giving the user
      a clear, actionable error rather than a cryptic traceback.
    * For composite sources (``ComplexComposite``, ``Pompe``): the string
      ``"--auto-flatten"`` must also appear in the output, hinting that the
      user can pass the flag to work around the limitation.
    * For orthogonal sources (``SimpleOrthogonal``): ``--auto-flatten`` must
      *not* be advertised, because it cannot help here.
    """
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
    """The ``--auto-flatten`` flag must enable generation for composite states
    and must keep failing for orthogonal regions.

    Sequence of calls
    -----------------
    1. ``SimpleComposite.plantuml cpp20 --auto-flatten`` — must succeed
       (returncode 0); simplest composite case, single level of nesting.
    2. ``ComplexComposite.plantuml cpp --auto-flatten`` — must succeed;
       deep composite nesting, C++11 backend.
    3. ``Pompe.plantuml cpp --auto-flatten`` — must succeed; composite with
       entry/exit actions.
    4. Pompe output content check: both the ``.hpp`` and ``.cpp`` for Pompe
       must contain the ``on_activity_default_id`` callback, confirming that
       flattening preserved the activity semantics and did not silently drop
       the state entry code.
    5. ``SimpleOrthogonal.plantuml cpp --auto-flatten`` — must *fail*
       (returncode != 0) with the message
       ``"Auto-flatten currently does not support orthogonal/concurrent
       regions"``, confirming that the flag does not over-promise.
    """

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
