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
"""Small file-emission helpers shared by generation code paths."""


def emit_to_file(parser, path, emitter, *args, **kwargs):
    """Run `emitter` while `parser.fd` points to an opened output file.

    The previous `parser.fd` value is restored after emission so callers can
    compose this helper safely inside larger generation workflows.
    """
    previous_fd = parser.fd
    try:
        with open(path, 'w') as stream:
            parser.fd = stream
            emitter(*args, **kwargs)
    finally:
        parser.fd = previous_fd
