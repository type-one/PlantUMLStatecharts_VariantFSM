###############################################################################
## PlantUML Statecharts (State Machine) Translator.
## Copyright (c) 2026 Laurent Lardinois <https://github.com/type-one>
## Original author: Quentin Quadrat <lecrapouille@gmail.com>
##
## This file is part of PlantUML Statecharts (State Machine) Translator.
##
## This tool is free software: you can redistribute it and/or modify it
## under the terms of the GNU General Public License as published by
## the Free Software Foundation, either version 3 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful, but
## WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
## General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program.  If not, see http://www.gnu.org/licenses/.
###############################################################################
"""
Generation contract tests.

These tests run the translator against small, well-known input diagrams and
assert structural properties of the emitted files that must hold across every
code-generation mode.  They are regression guards: if a refactor accidentally
changes includes, macro formatting, comment style, or indentation the failures
here are fast to diagnose because the expected text is spelled out explicitly.
"""

import re
import tempfile
from pathlib import Path


def test_generated_headers_contract(run_translator):
    """Verify that all four output modes produce well-formed file preambles.

    Exercises: ``SimpleFSM.plantuml`` × {hpp, hpp20, cpp, cpp20}.

    Include expectations
    --------------------
    * C++11 ``.hpp`` must include the C++11 state-machine header
      (``state_machine.hpp``) and its standard dependencies (``<array>``,
      ``<cassert>``, ``<map>``, etc.).
    * C++20 ``.hpp`` must include the variant header
      (``state_machine_variant.hpp``) and its standard dependencies
      (``<variant>``, ``<optional>``, ``<type_traits>``, etc.).

    MOCKABLE macro formatting
    -------------------------
    * The guard must expand to the single-line ``#define MOCKABLE`` form.
    * The indented ``#  define MOCKABLE`` (legacy two-space style) must be
      absent: any such reintroduction would indicate a regression in the
      macro template.

    Comment-style constraint
    ------------------------
    * All four files must use ``/**`` block-comment style.
    * Doxygen-style line-comment variants (``//! \\brief``, ``/// @brief``,
      ``//!<``, ``///<``) must be absent: the project standardized on ``/**``
      blocks after the documentation pass, and this assertion prevents silent
      regressions if a template is edited.
    """
    expected_hpp_includes = [
        '#include "state_machine.hpp"',
        '#include <array>',
        '#include <cassert>',
        '#include <cstdlib>',
        '#include <map>',
        '#include <mutex>',
        '#include <queue>',
        '#include <cstdio>',
    ]

    expected_hpp20_includes = [
        '#include "state_machine_variant.hpp"',
        '#include <cstdio>',
        '#include <cstring>',
        '#include <mutex>',
        '#include <optional>',
        '#include <type_traits>',
        '#include <utility>',
        '#include <variant>',
    ]

    with tempfile.TemporaryDirectory(prefix='fsm_gen_contract_') as out:
        out_path = Path(out)

        run_translator(['examples/SimpleFSM.plantuml', 'hpp', '-o', str(out_path)], check=True)
        hpp = (out_path / 'simple_fsm.hpp').read_text()

        run_translator(['examples/SimpleFSM.plantuml', 'hpp20', '-o', str(out_path)], check=True)
        hpp20 = (out_path / 'simple_fsm.hpp').read_text()

        run_translator(['examples/SimpleFSM.plantuml', 'cpp', '-o', str(out_path)], check=True)
        cpp = (out_path / 'simple_fsm.cpp').read_text()

        run_translator(['examples/SimpleFSM.plantuml', 'cpp20', '-o', str(out_path)], check=True)
        cpp20 = (out_path / 'simple_fsm.cpp').read_text()

    for inc in expected_hpp_includes:
        assert inc in hpp
    for inc in expected_hpp20_includes:
        assert inc in hpp20

    assert '#define MOCKABLE' in hpp
    assert '#define MOCKABLE' in hpp20
    assert '#  define MOCKABLE' not in hpp
    assert '#  define MOCKABLE' not in hpp20

    for generated in (hpp, hpp20, cpp, cpp20):
        assert '/**' in generated
        assert '//! \\brief' not in generated
        assert '/// @brief' not in generated
        assert '//!<' not in generated
        assert ' ///< ' not in generated
        assert '///< ' not in generated


def test_no_duplicate_variant_dispatch_lambdas(run_translator):
    """Regression: the C++20 visitor must emit each per-event lambda exactly once.

    Exercises: ``Triggers.plantuml`` in ``cpp20`` mode.

    Background: an earlier code-generation bug caused the same ``[this](a&)``
    dispatch lambda to be emitted twice inside the ``std::visit`` call when a
    state machine had multiple transitions on the same event type.  The second
    copy produced a hard compile error (duplicate lambda in overload set).

    Expectation:
    * The text ``[this](a&)`` (modulo whitespace between ``a`` and ``&``) must
      appear exactly once in ``triggers.cpp``.  Zero occurrences would mean
      the event is not dispatched at all; two or more would reproduce the
      duplicate-lambda bug.
    """
    with tempfile.TemporaryDirectory(prefix='fsm_reg_dupvis_') as out:
        out_path = Path(out)
        run_translator(['examples/Triggers.plantuml', 'cpp20', '-o', str(out_path)], check=True)
        cpp20 = (out_path / 'triggers.cpp').read_text()

    a_lambdas = re.findall(r'\[this\]\(a\s*&\)', cpp20)
    assert len(a_lambdas) == 1


def test_normalized_state_action_indent(run_translator):
    """Regression: on_entering_* action bodies must use 4-space indentation.

    Exercises: ``SimpleFSM.plantuml`` in ``cpp20`` mode.

    Background: a template change once caused ``on_entering_*`` bodies to be
    indented with 8 spaces (two levels) instead of 4 (one level), making the
    generated code inconsistently formatted compared to the rest of the file.

    Expectations:
    * ``action7();`` and ``action8();`` appear preceded by exactly four spaces
      (``    action7();\\n``).
    * The 8-space form (``        action7();\\n``) must be absent, confirming
      no double-indentation regression.
    """

    with tempfile.TemporaryDirectory(prefix='fsm_reg_indent_') as out:
        out_path = Path(out)
        run_translator(['examples/SimpleFSM.plantuml', 'cpp20', '-o', str(out_path)], check=True)
        cpp20 = (out_path / 'simple_fsm.cpp').read_text()

    assert '    action7();\n' in cpp20
    assert '        action7();\n' not in cpp20
    assert '    action8();\n' in cpp20
    assert '        action8();\n' not in cpp20
