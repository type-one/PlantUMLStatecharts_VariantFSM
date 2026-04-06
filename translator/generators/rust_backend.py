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
"""Rust backend orchestration (MVP).

Generates a minimal Rust FSM using:
- `enum State` for active-state representation,
- `struct <fsm>` holding current state and active flag,
- per-event `match self.state` dispatch,
- placeholder guard/action/entry/leave callback methods.
"""

import os
import re

from .io_helpers import emit_to_file


def _to_rust_variant(name):
    """Convert an identifier into a Rust enum variant (PascalCase)."""
    parts = re.split(r'[^A-Za-z0-9]+', name)
    merged = ''.join(p[:1].upper() + p[1:] for p in parts if p != '')
    if merged == '':
        merged = 'State'
    if merged[0].isdigit():
        merged = 'S' + merged
    return merged


def _rust_state_variant(parser, state):
    """Map PlantUML state token to Rust State enum variant name."""
    if state == '*':
        return 'Destructor'
    if state == '[*]':
        return 'Constructor'
    return _to_rust_variant(parser.state_name(state))


def _rust_escape(text):
    return text.replace('\\', '\\\\').replace('"', '\\"')


def _write_snippet_as_comments(parser, code, depth):
    """Preserve user snippet text as Rust comments in generated placeholders."""
    if code is None:
        return
    lines = [line.rstrip() for line in code.splitlines() if line.strip() != '']
    for line in lines:
        parser.indent(depth)
        parser.fd.write('// from PlantUML: ' + line + '\n')


def _write_extra_code_as_comments(parser, label, code, depth):
    """Emit a PlantUML extra-code section as a fenced Rust comment block."""
    if not code or not code.strip():
        return
    parser.indent(depth)
    parser.fd.write('// --- from PlantUML [' + label + '] (translate to Rust as needed) ---\n')
    for line in code.splitlines():
        parser.indent(depth)
        parser.fd.write('// ' + line + '\n')
    parser.indent(depth)
    parser.fd.write('// --- end [' + label + '] ---\n')


def _group_arcs_by_origin(arcs):
    grouped = {}
    for origin, destination in arcs:
        if origin in ('[*]',):
            continue
        grouped.setdefault(origin, []).append(destination)
    return grouped


def _emit_noevent_chain(parser, state, depth, visited=None):
    """Emit immediate no-event transitions from `state` (with optional chaining)."""
    if state in ('[*]', '*'):
        return
    if visited is None:
        visited = set()
    if state in visited:
        return

    next_visited = set(visited)
    next_visited.add(state)

    for dest in list(parser.current.graph.neighbors(state)):
        tr = parser.current.graph[state][dest]['data']
        if tr.event.name != '':
            continue

        if tr.guard != '':
            parser.indent(depth)
            parser.fd.write('if self.' + parser.guard_function(state, dest, False) + '() {\n')
            inner = depth + 1
        else:
            inner = depth

        src_data = parser.current.graph.nodes[state]['data']
        if src_data.leaving != '':
            parser.indent(inner)
            parser.fd.write('self.' + parser.state_leaving_function(state, False) + '();\n')
        if tr.action != '':
            parser.indent(inner)
            parser.fd.write('self.' + parser.transition_function(state, dest, False) + '();\n')

        parser.indent(inner)
        parser.fd.write('self.state = State::' + _rust_state_variant(parser, dest) + ';\n')

        if dest != '*':
            dest_data = parser.current.graph.nodes[dest]['data']
            if dest_data.entering != '':
                parser.indent(inner)
                parser.fd.write('self.' + parser.state_entering_function(dest, False) + '();\n')
            _emit_noevent_chain(parser, dest, inner, next_visited)

        if tr.guard != '':
            parser.indent(inner)
            parser.fd.write('return;\n')
            parser.indent(depth)
            parser.fd.write('}\n')
        else:
            # First unconditional no-event path wins.
            break


def _emit_transition_body(parser, origin, destination, depth):
    tr = parser.current.graph[origin][destination]['data']
    origin_data = parser.current.graph.nodes[origin]['data']
    dest_data = parser.current.graph.nodes[destination]['data']

    if origin == destination:
        if tr.action != '':
            parser.indent(depth)
            parser.fd.write('self.' + parser.transition_function(origin, destination) + '();\n')
        return

    if origin_data.leaving != '':
        parser.indent(depth)
        parser.fd.write('self.' + parser.state_leaving_function(origin, False) + '();\n')
    if tr.action != '':
        parser.indent(depth)
        parser.fd.write('self.' + parser.transition_function(origin, destination) + '();\n')

    parser.indent(depth)
    parser.fd.write('self.state = State::' + _rust_state_variant(parser, destination) + ';\n')

    if destination != '*' and dest_data.entering != '':
        parser.indent(depth)
        parser.fd.write('self.' + parser.state_entering_function(destination, False) + '();\n')
    _emit_noevent_chain(parser, destination, depth)


def _emit_event_method(parser, event, arcs):
    method_name = event.name
    params = event.params

    generic_decl = ''
    signature_params = ''
    keep_alive = ''
    if len(params) > 0:
        generic_names = ['T' + str(i) for i in range(len(params))]
        generic_decl = '<' + ', '.join(generic_names) + '>'
        signature_params = ', ' + ', '.join([params[i] + ': ' + generic_names[i] for i in range(len(params))])
        if len(params) == 1:
            keep_alive = 'let _ = ' + params[0] + ';\n'
        else:
            keep_alive = 'let _ = (' + ', '.join(params) + ');\n'

    parser.indent(1)
    parser.fd.write('pub fn ' + method_name + generic_decl + '(&mut self' + signature_params + ') {\n')
    if keep_alive != '':
        parser.indent(2)
        parser.fd.write(keep_alive)

    parser.indent(2)
    parser.fd.write('match self.state {\n')

    grouped = _group_arcs_by_origin(arcs)
    for origin, destinations in grouped.items():
        parser.indent(3)
        parser.fd.write('State::' + _rust_state_variant(parser, origin) + ' => {\n')
        for destination in destinations:
            tr = parser.current.graph[origin][destination]['data']
            if tr.guard != '':
                parser.indent(4)
                parser.fd.write('if self.' + parser.guard_function(origin, destination, False) + '() {\n')
                _emit_transition_body(parser, origin, destination, 5)
                parser.indent(5)
                parser.fd.write('return;\n')
                parser.indent(4)
                parser.fd.write('}\n')
            else:
                _emit_transition_body(parser, origin, destination, 4)
                parser.indent(4)
                parser.fd.write('return;\n')
                break
        parser.indent(3)
        parser.fd.write('}\n')

    parser.indent(3)
    parser.fd.write('_ => {}\n')
    parser.indent(2)
    parser.fd.write('}\n')
    parser.indent(1)
    parser.fd.write('}\n\n')


def _emit_initial_state_selection(parser, neighbors, depth):
    """Emit enter() initial-state selection from [*] transitions.

    Mirrors existing backend behavior:
    - single initial transition: direct assignment, or guarded assignment,
    - multiple initial transitions: evaluate guarded branches in order,
      with return on first match; unguarded branches are emitted directly.
    """
    if len(neighbors) == 0:
        return

    if len(neighbors) == 1:
        dest = neighbors[0]
        tr = parser.current.graph['[*]'][dest]['data']
        parser.indent(depth)
        if tr.guard != '':
            parser.fd.write('if self.' + parser.guard_function('[*]', dest, False) + '() {\n')
            inner = depth + 1
        else:
            parser.fd.write('{\n')
            inner = depth + 1

        parser.indent(inner)
        parser.fd.write('self.state = State::' + _rust_state_variant(parser, dest) + ';\n')
        dest_data = parser.current.graph.nodes[dest]['data']
        if dest_data.entering != '':
            parser.indent(inner)
            parser.fd.write('self.' + parser.state_entering_function(dest, False) + '();\n')
        _emit_noevent_chain(parser, dest, inner)

        parser.indent(depth)
        parser.fd.write('}\n')
        return

    for dest in neighbors:
        tr = parser.current.graph['[*]'][dest]['data']
        if tr.guard != '':
            parser.indent(depth)
            parser.fd.write('if self.' + parser.guard_function('[*]', dest, False) + '() {\n')
            inner = depth + 1
        else:
            inner = depth

        parser.indent(inner)
        parser.fd.write('self.state = State::' + _rust_state_variant(parser, dest) + ';\n')
        dest_data = parser.current.graph.nodes[dest]['data']
        if dest_data.entering != '':
            parser.indent(inner)
            parser.fd.write('self.' + parser.state_entering_function(dest, False) + '();\n')
        _emit_noevent_chain(parser, dest, inner)

        if tr.guard != '':
            parser.indent(inner)
            parser.fd.write('return;\n')
            parser.indent(depth)
            parser.fd.write('}\n')


def _emit_rust_machine(parser):
    states = [s for s in parser.current.graph.nodes if s != '[*]']
    if len(states) == 0:
        parser.fatal('Rust backend cannot generate an FSM with no concrete states')

    initial_neighbors = [n for n in parser.current.graph.neighbors('[*]') if n not in ('[*]', '*')]
    initial_state = initial_neighbors[0] if len(initial_neighbors) > 0 else states[0]

    parser.generate_common_header()
    parser.fd.write('// Rust backend (MVP) generated from PlantUML\n\n')
    parser.fd.write('#![allow(non_snake_case)]\n')
    parser.fd.write('#![allow(non_camel_case_types)]\n')
    parser.fd.write('#![allow(dead_code)]\n\n')

    _write_extra_code_as_comments(parser, 'header', parser.current.extra_code.header, 0)
    if parser.current.extra_code.header and parser.current.extra_code.header.strip():
        parser.fd.write('\n')

    if parser.current.extra_code.brief and parser.current.extra_code.brief.strip():
        parser.fd.write('//! ' + parser.current.extra_code.brief.strip() + '\n\n')

    parser.fd.write('#[derive(Debug, Clone, Copy, PartialEq, Eq)]\n')
    parser.fd.write('pub enum State {\n')
    for state in states:
        parser.fd.write('    ' + _rust_state_variant(parser, state) + ',\n')
    parser.fd.write('}\n\n')

    parser.fd.write('pub struct ' + parser.current.class_name + ' {\n')
    parser.fd.write('    pub state: State,\n')
    parser.fd.write('    enabled: bool,\n')
    parser.fd.write('}\n\n')

    parser.fd.write('impl ' + parser.current.class_name + ' {\n')
    parser.indent(1)
    parser.fd.write('pub fn new() -> Self {\n')
    parser.indent(2)
    parser.fd.write('let mut fsm = Self {\n')
    parser.indent(3)
    parser.fd.write('state: State::' + _rust_state_variant(parser, initial_state) + ',\n')
    parser.indent(3)
    parser.fd.write('enabled: false,\n')
    parser.indent(2)
    parser.fd.write('};\n')
    parser.indent(2)
    parser.fd.write('fsm.enter();\n')
    parser.indent(2)
    parser.fd.write('fsm\n')
    parser.indent(1)
    parser.fd.write('}\n\n')

    parser.indent(1)
    parser.fd.write('pub fn enter(&mut self) {\n')
    parser.indent(2)
    parser.fd.write('self.enabled = true;\n')
    _write_extra_code_as_comments(parser, 'init', parser.current.extra_code.init, 2)
    _emit_initial_state_selection(parser, initial_neighbors, 2)
    parser.indent(1)
    parser.fd.write('}\n\n')

    parser.indent(1)
    parser.fd.write('pub fn exit(&mut self) {\n')
    parser.indent(2)
    parser.fd.write('self.enabled = false;\n')
    parser.indent(1)
    parser.fd.write('}\n\n')

    parser.indent(1)
    parser.fd.write('pub fn is_active(&self) -> bool { self.enabled }\n\n')
    parser.indent(1)
    parser.fd.write('pub fn c_str(&self) -> &\'static str {\n')
    parser.indent(2)
    parser.fd.write('match self.state {\n')
    for state in states:
        parser.indent(3)
        parser.fd.write('State::' + _rust_state_variant(parser, state) + ' => "' + _rust_escape(state) + '",\n')
    parser.indent(2)
    parser.fd.write('}\n')
    parser.indent(1)
    parser.fd.write('}\n\n')

    # External events
    for event, arcs in parser.current.lookup_events.items():
        if event.name == '':
            continue
        _emit_event_method(parser, event, arcs)

    # Placeholder callbacks
    transitions = list(parser.current.graph.edges)
    for origin, destination in transitions:
        tr = parser.current.graph[origin][destination]['data']
        if tr.guard != '':
            parser.indent(1)
            parser.fd.write('fn ' + parser.guard_function(origin, destination, False) + '(&self) -> bool {\n')
            _write_snippet_as_comments(parser, tr.guard, 2)
            parser.indent(2)
            parser.fd.write('true\n')
            parser.indent(1)
            parser.fd.write('}\n\n')
        if tr.action != '':
            parser.indent(1)
            parser.fd.write('fn ' + parser.transition_function(origin, destination, False) + '(&mut self) {\n')
            _write_snippet_as_comments(parser, tr.action, 2)
            parser.indent(2)
            parser.fd.write('// TODO: implement Rust transition action\n')
            parser.indent(1)
            parser.fd.write('}\n\n')

    for node in parser.current.graph.nodes:
        if node in ('[*]', '*'):
            continue
        state = parser.current.graph.nodes[node]['data']
        if state.entering != '':
            parser.indent(1)
            parser.fd.write('fn ' + parser.state_entering_function(node, False) + '(&mut self) {\n')
            _write_snippet_as_comments(parser, state.entering, 2)
            parser.indent(2)
            parser.fd.write('// TODO: implement Rust entering action\n')
            parser.indent(1)
            parser.fd.write('}\n\n')
        if state.leaving != '':
            parser.indent(1)
            parser.fd.write('fn ' + parser.state_leaving_function(node, False) + '(&mut self) {\n')
            _write_snippet_as_comments(parser, state.leaving, 2)
            parser.indent(2)
            parser.fd.write('// TODO: implement Rust leaving action\n')
            parser.indent(1)
            parser.fd.write('}\n\n')

    _write_extra_code_as_comments(parser, 'code', parser.current.extra_code.code, 1)
    if parser.current.extra_code.code and parser.current.extra_code.code.strip():
        parser.fd.write('\n')

    parser.fd.write('}\n')

    _write_extra_code_as_comments(parser, 'footer', parser.current.extra_code.footer, 0)


def generate_rust_backend(parser, target, separated):
    """Generate Rust MVP artifacts (`.rs`) for all parsed machines."""
    del separated  # Rust MVP emits one file per machine; no separate test-main flow yet.
    del target

    for parser.current in parser.machines.values():
        filename = parser.current.class_name + '.rs'
        rust_target = os.path.join(parser.output_dir, filename)
        emit_to_file(parser, rust_target, lambda: _emit_rust_machine(parser))
