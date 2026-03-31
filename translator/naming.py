###############################################################################
## PlantUML Statecharts (State Machine) Translator.
## Copyright (c) 2022 Quentin Quadrat <lecrapouille@gmail.com>
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
"""Naming helpers used by the translator.

This module intentionally contains only pure naming utilities so they can be
shared by parser and generator code without dragging parser state.
"""

import re


def camel_to_snake(name):
    """Convert CamelCase or mixedCase identifiers to snake_case."""
    s1 = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    s2 = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', s1)
    return s2.lower()


CPP_RESERVED_IDENTIFIERS = {
    'alignas', 'alignof', 'and', 'and_eq', 'asm', 'auto',
    'bitand', 'bitor', 'bool', 'break', 'case', 'catch', 'char',
    'char8_t', 'char16_t', 'char32_t', 'class', 'compl', 'concept',
    'const', 'consteval', 'constexpr', 'constinit', 'const_cast',
    'continue', 'co_await', 'co_return', 'co_yield', 'decltype',
    'default', 'delete', 'do', 'double', 'dynamic_cast', 'else',
    'enum', 'explicit', 'export', 'extern', 'false', 'float', 'for',
    'friend', 'goto', 'if', 'inline', 'int', 'long', 'mutable',
    'namespace', 'new', 'noexcept', 'not', 'not_eq', 'nullptr',
    'operator', 'or', 'or_eq', 'private', 'protected', 'public',
    'register', 'reinterpret_cast', 'requires', 'return', 'short',
    'signed', 'sizeof', 'static', 'static_assert', 'static_cast',
    'struct', 'switch', 'template', 'this', 'thread_local', 'throw',
    'true', 'try', 'typedef', 'typeid', 'typename', 'union',
    'unsigned', 'using', 'virtual', 'void', 'volatile', 'wchar_t',
    'while', 'xor', 'xor_eq',
}
