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
"""Core statechart data model and graph checks.

The parser builds instances of these classes from PlantUML and the code
generator consumes them. Keeping them in a dedicated module reduces coupling
with code-emission logic.
"""

from collections import defaultdict

import networkx as nx


class bcolors:
    """ANSI colors used for warning messages."""

    WARNING = '\033[93m'
    ENDC = '\033[0m'


class Event(object):
    """Parsed event signature.

    Stores the normalized event name and the list of argument identifiers.
    """

    def __init__(self):
        self.name = ''
        self.params = []

    def parse(self, tokens):
        """Parse event tokens from AST into name and argument list."""
        self.params = []
        self.name = ''
        N = len(tokens)
        if N == 0:
            self.name = ''
            return
        for i in range(0, N):
            if tokens[i][0] == '(':
                if i != N - 1:
                    raise ValueError('Malformed event token sequence: argument list must be the last token')
                self.params = tokens[i].split('(')[1][:-1].split(',')
            elif i == 0:
                if i < N - 1 and tokens[i + 1][0] == '(':
                    self.name = tokens[i]
                else:
                    self.name += tokens[i].lower()
            else:
                self.name += tokens[i].capitalize()

    def header(self, name=None):
        """Return C++ method declaration string for the event."""
        params = ''
        for p in self.params:
            if params != '':
                params += ', '
            params += p.upper() + ' const& ' + p + '_'
        method = self.name if name is None else name
        return 'void ' + method + '(' + params + ')'

    def caller(self, var='', name=None):
        """Return C++ call expression for the event with optional prefix."""
        s = '' if var == '' else var + '.'
        params = ''
        for p in self.params:
            if params != '':
                params += ', '
            params += s + p
        method = self.name if name is None else name
        return method + '(' + params + ')'

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return isinstance(other, Event) and (self.name == other.name)

    def __str__(self):
        return self.definition()

    def __repr__(self):
        return self.definition()


class Transition(object):
    """Directed transition between two states with optional event/guard/action."""

    def __init__(self):
        self.origin = ''
        self.destination = ''
        self.event = Event()
        self.guard = ''
        self.action = ''
        self.count_guard = 0
        self.count_action = 0
        self.arrow = ''

    def __str__(self):
        if self.origin == self.destination:
            return self.origin + ' : on ' + self.event.name + \
                   ' [' + self.guard + '] / ' + self.action
        dest = '[*]' if self.destination == '*' else self.destination
        if self.arrow[-1] == '>':
            code = self.origin + ' ' + self.arrow + ' ' + dest
        else:
            code = dest + ' ' + self.arrow + ' ' + self.origin
        if self.event.name != '' or self.guard != '' or self.action != '':
            code += ' : '
        if self.event.name != '':
            code += self.event.name
        if self.guard != '':
            code += ' [' + self.guard + ']'
        if self.action != '':
            code += '\\n--\\n' + self.action
        return code


class State(object):
    """State metadata and attached behavior snippets."""

    def __init__(self, name):
        self.name = name
        self.comment = ''
        self.entering = ''
        self.leaving = ''
        self.activity = ''
        self.internal = ''
        self.count_entering = 0
        self.count_leaving = 0

    def __str__(self):
        code = ''
        if self.entering != '':
            code += self.name + ' : entering / ' + self.entering.strip()
        if self.leaving != '':
            if code != '':
                code += '\n'
            code += self.name + ' : leaving / ' + self.leaving.strip()
        if self.activity != '':
            if code != '':
                code += '\n'
            code += self.name + ' : activity / ' + self.activity.strip()
        return code


class ExtraCode(object):
    """User-injected C++ snippets grouped by insertion point."""

    def __init__(self):
        self.brief = ''
        self.header = ''
        self.footer = ''
        self.argvs = ''
        self.cons = ''
        self.init = ''
        self.code = ''
        self.unit_tests = ''


class StateMachine(object):
    """In-memory state machine model backed by a directed graph."""

    def __init__(self):
        # Node payloads are State objects, edge payloads are Transition objects.
        self.graph = nx.DiGraph()
        self.parent = None
        self.children = []
        self.initial_state = ''
        self.final_state = ''
        self.lookup_events = defaultdict(list)
        self.broadcasts = []
        self.name = ''
        self.class_name = ''
        self.enum_name = ''
        self.extra_code = ExtraCode()
        self.warnings = []

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name + ', I: ' + self.initial_state

    def is_composite(self):
        return False

    def add_state(self, name):
        """Insert a state node once and attach a State payload."""
        if not self.graph.has_node(name):
            self.graph.add_node(name, data=State(name))

    def add_transition(self, tr):
        """Insert a directed edge and attach its Transition payload."""
        self.graph.add_edge(tr.origin, tr.destination, data=tr)

    def graph_cycles(self):
        """Return cycles normalized to start from a child of initial state."""
        cycles = []
        for cycle in list(nx.simple_cycles(self.graph)):
            index = -1
            for n in self.graph.neighbors(self.initial_state):
                try:
                    index = cycle.index(n)
                    break
                except Exception as ValueError:
                    continue
            if index != -1:
                cycles.append(cycle[index:] + cycle[:index])
                cycles[-1].append(cycles[-1][0])
        return cycles

    def graph_dfs(self):
        """Return edges in depth-first order from the initial state."""
        return list(nx.dfs_edges(self.graph, source=self.initial_state))

    def graph_all_paths_to_sinks(self):
        """Return all source-to-sink simple paths."""
        all_paths = []
        sink_nodes = [node for node, outdegree in self.graph.out_degree(self.graph.nodes()) if outdegree == 0]
        source_nodes = [node for node, indegree in self.graph.in_degree(self.graph.nodes()) if indegree == 0]
        for (source, sink) in [(source, sink) for sink in sink_nodes for source in source_nodes]:
            for path in nx.all_simple_paths(self.graph, source=source, target=sink):
                all_paths.append(path)
        return all_paths

    def verify_initial_state(self):
        """Check initial-state constraints and emit warnings when missing."""
        if self.parent == None:
            if self.initial_state == '':
                self.warning('Missing initial state in the main state machine')
            return

    def verify_number_of_events(self):
        """Warn when no explicit event exists in the state machine."""
        for e in self.lookup_events:
            if e.name != '':
                return
        self.warning('The state machine shall have at least one event.')

    def verify_incoming_transitions(self):
        """Warn about unreachable states without incoming transitions."""
        for state in list(self.graph.nodes()):
            if state != '[*]' and len(list(self.graph.predecessors(state))) == 0:
                self.warning('The state ' + state + ' shall have at least one incoming transition')

    def verify_infinite_loops(self):
        """Detect cycles composed only of event-less transitions."""
        for cycle in self.graph_cycles():
            find = True
            if len(cycle) == 1:
                find = False
                continue
            for i in range(len(cycle) - 1):
                if self.graph[cycle[i]][cycle[i + 1]]['data'].event.name != '':
                    find = False
                    break
            if find == True:
                str = ' '.join(cycle) + ' '
                self.warning('The state machine has an infinite loop: ' + str + '. Add an event!')
                return

    def verify_transitions(self):
        """Warn about non-deterministic outgoing transitions."""
        for state in list(self.graph.nodes()):
            out = list(self.graph.neighbors(state))
            if len(out) <= 1:
                continue
            for d in out:
                tr = self.graph[state][d]['data']
                if (tr.event.name == '') and (tr.guard == ''):
                    self.warning('The state ' + state + ' has an issue with its transitions: it has' +
                                 ' several possible ways while the way to state ' + d +
                                 ' is always true and therefore will be always a candidate and transition' +
                                 ' to other states is non determinist.')

    def is_determinist(self):
        """Run all currently implemented structural checks."""
        self.verify_initial_state()
        self.verify_number_of_events()
        self.verify_incoming_transitions()
        self.verify_transitions()
        self.verify_infinite_loops()
        pass

    def warning(self, msg):
        """Record and print warning in a consistent format."""
        self.warnings.append(msg)
        print(f"{bcolors.WARNING}   WARNING in the state machine " + self.name
              + ": " + msg + f"{bcolors.ENDC}")
