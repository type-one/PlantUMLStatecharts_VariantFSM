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
"""Shared orchestration helpers for backend code generation.

The parser already provides concrete emitters (single-file mode, split mode,
and unit-test emitters). This module centralizes the repeated outer loop that
iterates over all machines and wires emitters consistently.
"""

import os


def generate_for_backend(parser,
                         cxxfile,
                         separated,
                         split_mode_builder,
                         single_mode_builder,
                         unit_tests_builder,
                         include_cpp_impl_in_files=False):
    """Generate backend artifacts for all parsed machines.

    Parameters:
        parser: Live parser instance holding machines and output config.
        cxxfile: Target mode (`cpp` for split, otherwise single-file mode).
        separated: When True, emits a dedicated main test file.
        split_mode_builder: Callable for split-mode code emission.
        single_mode_builder: Callable for single-file code emission.
        unit_tests_builder: Callable that emits tests for one machine.
        include_cpp_impl_in_files: Include generated .cpp in the tests index.
    """
    files = []
    for parser.current in parser.machines.values():
        test_file = parser.current.class_name + parser.tests_file_suffix()
        if cxxfile == 'cpp':
            # Split mode: emit .hpp + .cpp and generate tests next to headers.
            hpp_name = parser.current.class_name + '.hpp'
            cpp_name = parser.current.class_name + '.cpp'
            hpp_target = os.path.join(parser.output_dir, hpp_name)
            cpp_target = os.path.join(parser.output_dir, cpp_name)
            if include_cpp_impl_in_files:
                files.append(cpp_name)
            files.append(test_file)
            split_mode_builder(hpp_target, cpp_target)
            unit_tests_builder(hpp_target, files, separated)
        else:
            # Single-file mode: emit one target artifact and corresponding tests.
            files.append(test_file)
            filename = parser.current.class_name + '.' + cxxfile
            target = os.path.join(parser.output_dir, filename)
            single_mode_builder(target)
            unit_tests_builder(target, files, separated)

    if separated:
        # Optional global test main used when tests are emitted separately.
        mainfile = parser.master.class_name + 'MainTests.cpp'
        mainfile = os.path.join(parser.output_dir, mainfile)
        parser.generate_unit_tests_main_file(mainfile, files)
