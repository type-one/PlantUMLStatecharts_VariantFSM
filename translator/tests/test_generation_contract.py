import re
import tempfile
from pathlib import Path


def test_generated_headers_contract(run_translator):
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
    with tempfile.TemporaryDirectory(prefix='fsm_reg_dupvis_') as out:
        out_path = Path(out)
        run_translator(['examples/Triggers.plantuml', 'cpp20', '-o', str(out_path)], check=True)
        cpp20 = (out_path / 'triggers.cpp').read_text()

    a_lambdas = re.findall(r'\[this\]\(a\s*&\)', cpp20)
    assert len(a_lambdas) == 1


def test_normalized_state_action_indent(run_translator):
    with tempfile.TemporaryDirectory(prefix='fsm_reg_indent_') as out:
        out_path = Path(out)
        run_translator(['examples/SimpleFSM.plantuml', 'cpp20', '-o', str(out_path)], check=True)
        cpp20 = (out_path / 'simple_fsm.cpp').read_text()

    assert '    action7();\n' in cpp20
    assert '        action7();\n' not in cpp20
    assert '    action8();\n' in cpp20
    assert '        action8();\n' not in cpp20
