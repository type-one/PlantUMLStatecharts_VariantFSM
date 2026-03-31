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
"""C++11 backend orchestration.

This module keeps backend-specific wiring decisions while delegating the shared
machine-iteration flow to `shared.generate_for_backend`.
"""

from .shared import generate_for_backend


def generate_cpp11_backend(parser, cxxfile, separated):
    """Generate C++11 artifacts (state machine files and unit tests).

    Notes:
        - `cpp` mode emits split files (`.hpp` + `.cpp`).
        - Non-`cpp` modes emit single-file artifacts.
        - The C++ implementation file is included in the tests list so split
          C++11 builds keep expected linkage behavior.
    """
    generate_for_backend(
        parser,
        cxxfile,
        separated,
        split_mode_builder=parser.generate_state_machine_split,
        single_mode_builder=parser.generate_state_machine,
        unit_tests_builder=parser.generate_unit_tests,
        include_cpp_impl_in_files=True,
    )
