###############################################################################
## PlantUML Statecharts (State Machine) Translator.
## Copyright (c) 2026 Laurent Lardinois <https://github.com/type-one>
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
"""C++20 variant backend orchestration.

This backend shares the same outer generation flow as C++11, but uses variant
emitters and enforces the flat-FSM-only constraint.
"""

from .shared import generate_for_backend


def generate_cpp20_backend(parser, cxxfile, separated):
    """Generate C++20 variant artifacts (state machine files and unit tests)."""
    # Variant backend currently supports only flat FSM diagrams.
    if parser.master.children:
        parser.fatal('C++20 variant backend does not support composite/hierarchical '
                     'state machines. Only flat FSM diagrams are supported.')

    generate_for_backend(
        parser,
        cxxfile,
        separated,
        split_mode_builder=parser.generate_variant_state_machine_split,
        single_mode_builder=parser.generate_variant_state_machine,
        unit_tests_builder=parser.generate_variant_unit_tests,
        include_cpp_impl_in_files=False,
    )
