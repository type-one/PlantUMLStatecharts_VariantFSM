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
"""Command-line argument parsing and dispatch for the translator."""

import sys


ALLOWED_TARGETS = ['cpp', 'hpp', 'cpp20', 'hpp20']


def usage(prog=None):
    """Print CLI usage information and terminate with error status."""
    if prog is None:
        prog = sys.argv[0]
    print('Command line: ' + prog + ' <plantuml file> cpp|hpp|cpp20|hpp20 [postfix] [-o <output_dir>] [-s|--snake] [-c|--camel] [-n <namespace>] [--thread-safe] [--auto-flatten] [--clang-format|--check-clang-format]')
    print('Where:')
    print('   <plantuml file>: the path of a plantuml statechart')
    print('   "cpp"           : generate C++11 split output (.hpp + .cpp include unit)')
    print('   "hpp"           : generate C++11 class-based header (single-file mode)')
    print('   "hpp20"         : generate C++20 std::variant/std::visit state machine (self-contained header)')
    print('   "cpp20"         : generate C++20 std::variant/std::visit split output (.hpp + .cpp stub)')
    print('   [postfix]: is an optional postfix to extend the name of the state machine class')
    print('   [-o <output_dir>]: optional output directory for generated files')
    print('   [-s|--snake]: use snake_case naming for generated symbols (default)')
    print('   [-c|--camel]: use CamelCase naming for generated symbols')
    print('   [-n|--namespace <namespace>]: optional C++ namespace for generated class')
    print('   [--thread-safe]: generate mutex-protected FSM code')
    print('   [--auto-flatten]: attempt to flatten hierarchical composites into a flat FSM before generation (orthogonal regions are still unsupported)')
    print('   [--clang-format]: run clang-format -i on generated .hpp/.cpp files in output directory')
    print('   [--check-clang-format]: check generated .hpp/.cpp formatting with clang-format --dry-run --Werror')
    print('Example:')
    print('   ' + prog + ' foo.plantuml cpp Bar')
    print('Will create foo_bar.hpp and foo_bar.cpp with a state machine name foo_bar (default snake_case)')
    print('   ' + prog + ' foo.plantuml hpp20 Bar -o ../build/generated')
    print('Will create generated files in ../build/generated')
    sys.exit(-1)


def parse_args(argv):
    """Parse CLI arguments into translation options.

    This parser intentionally preserves the historical CLI behavior and option
    order accepted by the project.
    """
    argc = len(argv)
    if argc < 3:
        usage(argv[0] if argc > 0 else None)

    if argv[2] not in ALLOWED_TARGETS:
        print('Invalid ' + argv[2] + '. Please set instead "cpp"/"hpp" (C++11) or "cpp20"/"hpp20" (C++20 std::variant)')
        usage(argv[0])

    opts = {
        'uml_file': argv[1],
        'cpp_or_hpp': argv[2],
        'postfix': '',
        'output_dir': '.',
        'snake_case': True,
        'namespace': '',
        'gen_mode': 'inline',
        'clang_format_mode': 'off',
        'thread_safe': False,
        'auto_flatten': False,
    }

    i = 3
    while i < argc:
        arg = argv[i]
        if arg in ['-o', '--output-dir']:
            if i + 1 >= argc:
                print('Missing value for ' + arg)
                usage(argv[0])
            opts['output_dir'] = argv[i + 1]
            i += 2
            continue
        if arg in ['-s', '--snake']:
            opts['snake_case'] = True
            i += 1
            continue
        if arg in ['-c', '--camel']:
            opts['snake_case'] = False
            i += 1
            continue
        if arg in ['-n', '--namespace']:
            if i + 1 >= argc:
                print('Missing value for ' + arg)
                usage(argv[0])
            opts['namespace'] = argv[i + 1]
            i += 2
            continue
        if arg == '--clang-format':
            opts['clang_format_mode'] = 'format'
            i += 1
            continue
        if arg == '--check-clang-format':
            opts['clang_format_mode'] = 'check'
            i += 1
            continue
        if arg == '--thread-safe':
            opts['thread_safe'] = True
            i += 1
            continue
        if arg == '--auto-flatten':
            opts['auto_flatten'] = True
            i += 1
            continue

        if opts['postfix'] == '':
            opts['postfix'] = arg
            i += 1
            continue

        print('Unexpected argument: ' + arg)
        usage(argv[0])

    return opts


def run(parser_cls, argv=None):
    """Dispatch translation from CLI arguments using the provided parser class."""
    if argv is None:
        argv = sys.argv
    opts = parse_args(argv)
    parser = parser_cls()
    parser.translate(
        opts['uml_file'],
        opts['cpp_or_hpp'],
        opts['postfix'],
        opts['output_dir'],
        snake_case=opts['snake_case'],
        namespace=opts['namespace'],
        gen_mode=opts['gen_mode'],
        clang_format_mode=opts['clang_format_mode'],
        thread_safe=opts['thread_safe'],
        auto_flatten=opts['auto_flatten'],
    )
