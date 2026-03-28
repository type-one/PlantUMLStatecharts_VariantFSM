#!/usr/bin/env python3

from lark import Lark, Transformer
import os, sys
import subprocess
import tempfile
from pathlib import Path

def check(exp):
    if not exp:
        raise Exception()

def check_AST(root):
    # The 'start' rule now directly contains all children (grammar removed the
    # intermediate state_diagram wrapper node).
    check(root.data == 'start')
    check(len(root.children) == 21)
    c = 0

    # ' this is a comment
    check(root.children[c].data == 'comment')
    c += 1

    # '[header] this is a header 1
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[header]')
    check(root.children[c].children[1].strip() == 'this is a header 1')
    c += 1

    # '[header] this is a header 2
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[header]')
    check(root.children[c].children[1].strip() == 'this is a header 2')
    c += 1

    # '[footer] this is a footer 1
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[footer]')
    check(root.children[c].children[1].strip() == 'this is a footer 1')
    c += 1

    # '[footer] this is a footer 2
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[footer]')
    check(root.children[c].children[1].strip() == 'this is a footer 2')
    c += 1

    # '[init] a = 0;
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[init]')
    check(root.children[c].children[1].strip() == 'a = 0;')
    c += 1

    # '[init] b = "ff";
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[init]')
    check(root.children[c].children[1].strip() == 'b = "ff";')
    c += 1

    # '[code] int foo();
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[code]')
    check(root.children[c].children[1].strip() == 'int foo();')
    c += 1

    # '[code] virtual std::string foo(std::foo<Bar> const& arg[]) = 0;
    check(root.children[c].data == 'cpp')
    check(len(root.children[c].children) == 2)
    check(root.children[c].children[0] == '[code]')
    check(root.children[c].children[1].strip() == 'virtual std::string foo(std::foo<Bar> const& arg[]) = 0;')
    c += 1

    # [*] --> State1
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 3)
    check(root.children[c].children[0] == '[*]')
    check(root.children[c].children[1] == '-->')
    check(root.children[c].children[2] == 'State1')
    c += 1

    # State1 --> State2
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 3)
    check(root.children[c].children[0] == 'State1')
    check(root.children[c].children[1] == '-->')
    check(root.children[c].children[2] == 'State2')
    c += 1

    # State2 -> State3 : / action = 1/3
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 4)
    check(root.children[c].children[0] == 'State2')
    check(root.children[c].children[1] == '->')
    check(root.children[c].children[2] == 'State3')
    check(root.children[c].children[3].data == 'uml_action')
    check(len(root.children[c].children[3].children) == 1)
    check(root.children[c].children[3].children[0] == '/ action = 1/3')
    c += 1

    # State3 <- State4 : [a[0] + b[] + c(3)]
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 4)
    check(root.children[c].children[0] == 'State3')
    check(root.children[c].children[1] == '<-')
    check(root.children[c].children[2] == 'State4')
    check(root.children[c].children[3].data == 'guard')
    check(len(root.children[c].children[3].children) == 1)
    check(root.children[c].children[3].children[0] == '[a[0] + b[] + c(3)]')
    c += 1

    # State4 <-- State5 : [a[0] + b[] + c(3)] / action = 1/3
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 5)
    check(root.children[c].children[0] == 'State4')
    check(root.children[c].children[1] == '<--')
    check(root.children[c].children[2] == 'State5')
    check(root.children[c].children[3].data == 'guard')
    check(len(root.children[c].children[3].children) == 1)
    check(root.children[c].children[3].children[0] == '[a[0] + b[] + c(3)]')
    check(root.children[c].children[4].data == 'uml_action')
    check(len(root.children[c].children[4].children) == 1)
    check(root.children[c].children[4].children[0] == '/ action = 1/3')
    c += 1

    # State5 --> State6 : setpoint(x, y)
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 4)
    check(root.children[c].children[0] == 'State5')
    check(root.children[c].children[1] == '-->')
    check(root.children[c].children[2] == 'State6')
    check(root.children[c].children[3].data == 'event')
    check(len(root.children[c].children[3].children) == 2)
    check(root.children[c].children[3].children[0] == 'setpoint')
    check(root.children[c].children[3].children[1] == '(x, y)')
    c += 1

    # State6 --> State7 : foo bar()
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 4)
    check(root.children[c].children[0] == 'State6')
    check(root.children[c].children[1] == '-->')
    check(root.children[c].children[2] == 'State7')
    check(root.children[c].children[3].data == 'event')
    check(len(root.children[c].children[3].children) == 3)
    check(root.children[c].children[3].children[0] == 'foo')
    check(root.children[c].children[3].children[1] == 'bar')
    check(root.children[c].children[3].children[2] == '()')
    c += 1

    # State8 <- State7 : foo bar / foo(a, 2[]) + "bar"; gg
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 5)
    check(root.children[c].children[0] == 'State8')
    check(root.children[c].children[1] == '<-')
    check(root.children[c].children[2] == 'State7')
    check(root.children[c].children[3].data == 'event')
    check(len(root.children[c].children[3].children) == 2)
    check(root.children[c].children[3].children[0] == 'foo')
    check(root.children[c].children[3].children[1] == 'bar')
    check(root.children[c].children[4].data == 'uml_action')
    check(len(root.children[c].children[4].children) == 1)
    check(root.children[c].children[4].children[0] == '/ foo(a, 2[]) + "bar"; gg')
    c += 1

    # State9 <- State8 : foo bar [a[0] + b[] + c(3)]
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 5)
    check(root.children[c].children[0] == 'State9')
    check(root.children[c].children[1] == '<-')
    check(root.children[c].children[2] == 'State8')
    check(root.children[c].children[3].data == 'event')
    check(len(root.children[c].children[3].children) == 2)
    check(root.children[c].children[3].children[0] == 'foo')
    check(root.children[c].children[3].children[1] == 'bar')
    check(root.children[c].children[4].data == 'guard')
    check(len(root.children[c].children[4].children) == 1)
    check(root.children[c].children[4].children[0] == '[a[0] + b[] + c(3)]')
    c += 1

    # State10 --> State9 : foo bar [a[0] + b[] + c(3)] / foo(a, a[2] / 2) + "bar"; gg
    # FIXME broken grammar:
    # FIXME guard shall be: [a[0] + b[] + c(3)]
    # FIXME action shall be: / foo(a, a[2] / 2) + "bar"; gg
    check(root.children[c].data == 'transition')
    check(len(root.children[c].children) == 6)
    check(root.children[c].children[0] == 'State10')
    check(root.children[c].children[1] == '-->')
    check(root.children[c].children[2] == 'State9')
    check(root.children[c].children[3].data == 'event')
    check(len(root.children[c].children[3].children) == 2)
    check(root.children[c].children[3].children[0] == 'foo')
    check(root.children[c].children[3].children[1] == 'bar')
    check(root.children[c].children[4].data == 'guard')
    check(len(root.children[c].children[4].children) == 1)
    check(root.children[c].children[4].children[0] == '[a[0] + b[] + c(3)] / foo(a, a[2]')
    check(root.children[c].children[5].data == 'uml_action')
    check(len(root.children[c].children[5].children) == 1)
    check(root.children[c].children[5].children[0] == '/ 2) + "bar"; gg')
    c += 1

    # state State11 {
    #   [*] -> ON
    #   ON -> OFF : off
    #   OFF -> ON : on
    # }
    # Grammar changed: state_block now holds [StateName, transition...] directly
    # instead of [StateName, state_diagram([transitions])].
    check(root.children[c].data == 'state_block')
    check(len(root.children[c].children) == 4)  # Token + 3 transitions
    check(str(root.children[c].children[0]) == 'State11')

    c0 = root.children[c].children[1]
    check(c0.data == 'transition')
    check(len(c0.children) == 3)
    check(c0.children[0] == '[*]')
    check(c0.children[1] == '->')
    check(c0.children[2] == 'ON')

    c1 = root.children[c].children[2]
    check(c1.data == 'transition')
    check(len(c1.children) == 4)
    check(c1.children[0] == 'ON')
    check(c1.children[1] == '->')
    check(c1.children[2] == 'OFF')
    check(len(c1.children[3].children) == 1)
    check(c1.children[3].data == 'event')
    check(len(c1.children[3].children) == 1)
    check(c1.children[3].children[0] == 'off')

    c2 = root.children[c].children[3]
    check(c2.data == 'transition')
    check(len(c2.children) == 4)
    check(c2.children[0] == 'OFF')
    check(c2.children[1] == '->')
    check(c2.children[2] == 'ON')
    check(len(c2.children[3].children) == 1)
    check(c2.children[3].data == 'event')
    check(len(c2.children[3].children) == 1)
    check(c2.children[3].children[0] == 'on')
    c += 1

    # state Active {
    #   [*] -> NumLockOff
    #   NumLockOff --> NumLockOn : EvNumLockPressed
    #   NumLockOn --> NumLockOff : EvNumLockPressed
    #   --
    #   [*] -> CapsLockOff
    #   CapsLockOff --> CapsLockOn : EvCapsLockPressed
    #   CapsLockOn --> CapsLockOff : EvCapsLockPressed
    #   --
    #   [*] -> ScrollLockOff
    #   ScrollLockOff --> ScrollLockOn : EvCapsLockPressed
    #   ScrollLockOn --> ScrollLockOff : EvCapsLockPressed
    # }
#    check(root.children[c].data == 'state_block')
#    check(len(root.children[c].children) == 2)
#    check(root.children[c].children[0] == 'Active')
#    check(root.children[c].children[1].data == 'state_diagram')
#    check(len(root.children[c].children[1].children) == 5)
#    check(root.children[c].children[1].children[0].data == 'ortho_block')
#    print(root.children[c].children[1].children[0].children)
#    check(len(root.children[c].children[1].children[0].children) == 6)
#    check(root.children[c].children[1].children[0].children[0].data == 'transition')
#    c0 = root.children[c].children[1].children[0].children[0]
#    check(c0.children[0] == '[*]')
#    check(c0.children[1] == '->')
#    check(c0.children[2] == 'NumLockOff')

def check_generated_headers_contract():
    repo_root = Path(__file__).resolve().parents[2]
    translator = repo_root / 'translator' / 'statecharts.py'
    source = repo_root / 'examples' / 'SimpleFSM.plantuml'

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

        subprocess.run(
            ['python3', str(translator), str(source), 'hpp', '-o', str(out_path)],
            check=True,
            cwd=repo_root,
        )
        hpp = (out_path / 'simple_fsm.hpp').read_text()

        subprocess.run(
            ['python3', str(translator), str(source), 'hpp20', '-o', str(out_path)],
            check=True,
            cwd=repo_root,
        )
        hpp20 = (out_path / 'simple_fsm.hpp').read_text()

        subprocess.run(
            ['python3', str(translator), str(source), 'cpp', '-o', str(out_path)],
            check=True,
            cwd=repo_root,
        )
        cpp = (out_path / 'simple_fsm.cpp').read_text()

        subprocess.run(
            ['python3', str(translator), str(source), 'cpp20', '-o', str(out_path)],
            check=True,
            cwd=repo_root,
        )
        cpp20 = (out_path / 'simple_fsm.cpp').read_text()

    for inc in expected_hpp_includes:
        check(inc in hpp)
    for inc in expected_hpp20_includes:
        check(inc in hpp20)

    check('#define MOCKABLE' in hpp)
    check('#define MOCKABLE' in hpp20)
    check('#  define MOCKABLE' not in hpp)
    check('#  define MOCKABLE' not in hpp20)

    for generated in (hpp, hpp20, cpp, cpp20):
        check('/// @brief' in generated)
        check('//! \\brief' not in generated)
        check('//!<' not in generated)
        check(' //!< ' not in generated)

def main():
    f = open('../statecharts.ebnf')
    parser = Lark(f.read())
    f = open('grammar.plantuml')
    ast = parser.parse(f.read())
    print("AST:", ast.pretty())
    # The 'start' rule directly contains all top-level children (no intermediate
    # state_diagram wrapper since grammar refactoring removed that layer).
    check(ast.data == 'start')
    check_AST(ast)
    check_generated_headers_contract()

if __name__ == '__main__':
    main()
