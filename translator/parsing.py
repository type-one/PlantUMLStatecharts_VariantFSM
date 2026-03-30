"""Parsing and AST-normalization mixin for the translator.

This module groups responsibilities related to:
- validating unsupported AST features,
- optional auto-flatten normalization,
- parsing AST nodes into StateMachine model objects,
- post-parse normalization for no-event transitions.
"""

import itertools

try:
    from .model import Transition, StateMachine
except ImportError:
    from model import Transition, StateMachine


class ParsingMixin:
    """Reusable parsing/normalization behavior for the main Parser class."""

    def assert_supported_diagram(self, auto_flatten=False):
        """Fail fast when the AST contains unsupported non-flat statechart features."""
        unsupported = set()

        def visit(node):
            data = getattr(node, 'data', None)
            if data == 'state_block':
                unsupported.add('composite/hierarchical states (state blocks)')
            elif data == 'ortho_block':
                unsupported.add('orthogonal/concurrent regions')
            for child in getattr(node, 'children', []):
                if hasattr(child, 'children'):
                    visit(child)

        visit(self.ast)

        if unsupported:
            details = '; '.join(sorted(unsupported))
            hint = ''
            if ('composite/hierarchical states (state blocks)' in unsupported) and (not auto_flatten):
                hint = ' Try again with --auto-flatten for hierarchical/composite diagrams.'
            self.fatal('Unsupported PlantUML diagram features detected: ' + details +
                       '. This translator currently supports only flat FSM diagrams '
                       '(no nested/composite/orthogonal regions).' + hint)

    def _transition_suffix_from_ast(self, inst):
        """Build the textual suffix of a transition from event/guard/action AST nodes."""
        if len(inst.children) <= 3:
            return ''
        parts = []
        for c in inst.children[3:]:
            if c.data == 'event':
                parts.append(' '.join([str(x) for x in c.children]))
            else:
                parts.append(str(c.children[0]))
        return ' : ' + ' '.join(parts)

    def _flatten_state_action_line(self, inst, state_name):
        """Convert a state action node into one flattened PlantUML action line."""
        what = inst.data[6:]
        if what in ['entry', 'entering']:
            return state_name + ' : entry ' + str(inst.children[1].children[0])
        if what in ['exit', 'leaving']:
            return state_name + ' : exit ' + str(inst.children[1].children[0])
        if what == 'comment':
            if len(inst.children) == 1:
                return state_name + ' : comment'
            return state_name + ' : comment ' + str(inst.children[1].children[0])
        if what in ['do', 'activity']:
            return state_name + ' : do ' + str(inst.children[1].children[0])
        if what in ['on', 'event']:
            out = state_name + ' : on '
            out += ' '.join([str(x) for x in inst.children[1].children])
            for i in range(2, len(inst.children)):
                if inst.children[i].data == 'guard':
                    out += ' ' + str(inst.children[i].children[0])
                elif inst.children[i].data in ['uml_action', 'std_action']:
                    out += ' ' + str(inst.children[i].children[0])
            return out
        self.fatal('Auto-flatten does not manage state action token ' + inst.data)

    def _flatten_block(self, children, is_top=False, prefix=''):
        """Flatten one composite state block into flat transition/action lines.

        The algorithm resolves composite origins to all leaf descendants and
        composite destinations to initial active leaf states.
        """
        child_blocks = {}
        for inst in children:
            if getattr(inst, 'data', None) == 'state_block':
                child_blocks[str(inst.children[0]).upper()] = inst

        local_leaf_names = set()
        for item in children:
            data = getattr(item, 'data', None)
            if data == 'transition':
                o = str(item.children[0]).upper()
                d = str(item.children[2]).upper()
                if o not in ['[*]', '*'] and o not in child_blocks:
                    local_leaf_names.add(o)
                if d not in ['[*]', '*'] and d not in child_blocks:
                    local_leaf_names.add(d)
            elif data and data.startswith('state_') and data != 'state_block':
                s = str(item.children[0]).upper()
                if s not in child_blocks:
                    local_leaf_names.add(s)

        def direct_initial_targets(block_children):
            targets = []
            for item in block_children:
                if getattr(item, 'data', None) != 'transition':
                    continue
                if str(item.children[0]).upper() == '[*]':
                    targets.append(str(item.children[2]).upper())
            return targets

        def leaves_for_block(block_inst, block_prefix):
            block_children = block_inst.children[1:]
            local_child_blocks = {}
            for item in block_children:
                if getattr(item, 'data', None) == 'state_block':
                    local_child_blocks[str(item.children[0]).upper()] = item

            local_leafs = set()
            for item in block_children:
                data = getattr(item, 'data', None)
                if data == 'transition':
                    o = str(item.children[0]).upper()
                    d = str(item.children[2]).upper()
                    if o not in ['[*]', '*'] and o not in local_child_blocks:
                        local_leafs.add(o)
                    if d not in ['[*]', '*'] and d not in local_child_blocks:
                        local_leafs.add(d)
                elif data and data.startswith('state_') and data != 'state_block':
                    s = str(item.children[0]).upper()
                    if s not in local_child_blocks:
                        local_leafs.add(s)

            leaves = set()
            for item in block_children:
                data = getattr(item, 'data', None)
                if data == 'state_block':
                    child_name = str(item.children[0]).upper()
                    leaves |= leaves_for_block(item, block_prefix + child_name + '_')
                elif data in ['transition'] or (data and data.startswith('state_') and data != 'state_block'):
                    for leaf in local_leafs:
                        leaves.add(block_prefix + leaf)
            if len(leaves) == 0:
                leaves.add(block_prefix[:-1])
            return leaves

        def initial_leaves_for_block(block_inst, block_prefix):
            block_children = block_inst.children[1:]
            local_child_blocks = {}
            for item in block_children:
                if getattr(item, 'data', None) == 'state_block':
                    local_child_blocks[str(item.children[0]).upper()] = item

            result = set()
            for target in direct_initial_targets(block_children):
                if target in local_child_blocks:
                    result |= initial_leaves_for_block(local_child_blocks[target], block_prefix + target + '_')
                else:
                    result.add(block_prefix + target)
            if len(result) == 0 and len(block_children) == 0:
                result.add(block_prefix[:-1])
            if len(result) == 0:
                self.fatal('Auto-flatten requires each composite state to define an initial transition [*] -> State')
            return result

        def resolve_origins(name):
            name = name.upper()
            if name in child_blocks:
                return sorted(leaves_for_block(child_blocks[name], prefix + name + '_'))
            if name in local_leaf_names:
                return [prefix + name]
            return [name]

        def resolve_dests(name):
            name = name.upper()
            if name in child_blocks:
                return sorted(initial_leaves_for_block(child_blocks[name], prefix + name + '_'))
            if name in local_leaf_names:
                return [prefix + name]
            return [name]

        lines = []

        for inst in children:
            if getattr(inst, 'data', None) == 'state_block':
                child_name = str(inst.children[0]).upper()
                lines.extend(self._flatten_block(inst.children[1:], False, prefix + child_name + '_'))

        for inst in children:
            data = getattr(inst, 'data', None)
            if data == 'transition':
                origin = str(inst.children[0]).upper()
                arrow = str(inst.children[1])
                dest = str(inst.children[2]).upper()

                if (not is_top) and origin == '[*]':
                    continue

                origins = resolve_origins(origin)
                dests = resolve_dests(dest)
                suffix = self._transition_suffix_from_ast(inst)

                for o in origins:
                    for d in dests:
                        lines.append(o + ' ' + arrow + ' ' + d + suffix)
            elif data and data.startswith('state_') and data != 'state_block':
                state_name = str(inst.children[0]).upper()
                mapped = resolve_origins(state_name)
                for s in mapped:
                    lines.append(self._flatten_state_action_line(inst, s))
            elif data in ['comment', 'note', 'ortho_block']:
                if data == 'ortho_block':
                    self.fatal('Auto-flatten currently does not support orthogonal/concurrent regions')
                continue

        return lines

    def auto_flatten_unsupported_diagram(self):
        """Rewrite the current AST as an equivalent flat FSM when auto-flatten is enabled."""
        flattened = ['@startuml']
        operational = []
        for inst in self.ast.children:
            data = getattr(inst, 'data', None)
            if data == 'cpp':
                flattened.append("'" + str(inst.children[0]) + ' ' + str(inst.children[1]).strip())
            elif data == 'comment':
                flattened.append("'" + str(inst.children[0]))
            elif data == 'skin':
                flattened.append('skin ' + str(inst.children[0]))
            elif data in ['state_block', 'transition'] or (data and data.startswith('state_') and data != 'state_block'):
                operational.append(inst)
            elif data == 'ortho_block':
                self.fatal('Auto-flatten currently does not support orthogonal/concurrent regions')
            elif data in ['note']:
                continue
        flattened.extend(self._flatten_block(operational, True, ''))
        flattened.append('@enduml')

        try:
            self.ast = self.parser.parse('\n'.join(flattened) + '\n')
        except Exception as ex:
            self.fatal('Auto-flatten failed to produce a valid intermediate diagram: ' + str(ex))

    def manage_noevents(self):
        """Translate no-event outgoing edges into generated internal transition code."""
        states = []
        for state in list(self.current.graph.nodes()):
            for dest in list(self.current.graph.neighbors(state)):
                tr = self.current.graph[state][dest]['data']
                if (tr.event.name == '') and (state not in states):
                    states.append(state)

        for state in states:
            count = 0
            code = ''
            for dest in list(self.current.graph.neighbors(state)):
                tr = self.current.graph[state][dest]['data']
                if tr.event.name != '':
                    continue
                if tr.guard != '':
                    if code == '':
                        code += '        if '
                    else:
                        code += '        else if '
                    code += '(' + self.guard_function(state, dest) + '())\n'
                elif tr.event.name == '':
                    if count == 1:
                        code += '\n#warning "Missformed state machine: missing guard from state ' + state + ' to state ' + dest + '"\n'
                        code += '        /* MISSING GUARD: if (guard) */\n'
                    elif count > 1:
                        code += '\n#warning "Undeterminist State machine detected switching from state ' + state + ' to state ' + dest + '"\n'
                if tr.event.name == '':
                    code += '        {\n'
                    code += '            FSM_LOGD("[' + self.current.class_name.upper() + '][STATE ' + state + '] Candidate for internal transitioning to state ' + dest + '\\n");\n'
                    code += '            static const struct ' + self.runtime_base_class_qualified_name() + '<' + self.runtime_base_template_arguments() + '>::' + self.runtime_transition_type() + ' tr =\n'
                    code += '            {\n'
                    code += '                .destination = ' + self.state_enum(dest) + ',\n'
                    if tr.action != '':
                        code += '                .action = &' + self.transition_function(state, dest, True) + ',\n'
                    code += '            };\n'
                    code += '            transition(&tr);\n'
                    code += '        }\n'
                    count += 1
            self.current.graph.nodes[state]['data'].internal += code

    def check_valid_method_name(self, name):
        """Warn when a generated callback name collides with runtime base API names."""
        s = name.split('(')[0]
        if s in ['start', 'stop', 'state', 'c_str', 'transition']:
            self.warning('The C++ method name ' + name + ' is already used by the base class ' + self.runtime_base_class_name())

    def parse_transition(self, as_state=False):
        """Parse tokenized transition data and append a Transition to the current graph."""
        tr = Transition()

        tr.arrow = self.tokens[1]
        if tr.arrow[-1] == '>':
            tr.origin, tr.destination = self.tokens[0].upper(), self.tokens[2].upper()
        else:
            tr.origin, tr.destination = self.tokens[2].upper(), self.tokens[0].upper()

        if tr.origin == '[*]':
            self.current.initial_state = '[*]'
        elif tr.destination == '[*]':
            tr.destination = '*'
            self.current.final_state = '*'

        self.current.add_state(tr.origin)
        self.current.add_state(tr.destination)

        for i in range(3, len(self.tokens)):
            if self.tokens[i] == '#event':
                N = int(self.tokens[i + 1])
                tr.event.parse(self.tokens[i + 2:i + 2 + N])
                tr.event.name = self.fmt_name(tr.event.name)
                self.check_valid_method_name(tr.event.name)
                if self.current.parent != None:
                    self.master.broadcasts.append((self.current.name, tr.event))
                self.current.lookup_events[tr.event].append((tr.origin, tr.destination))
            elif self.tokens[i] == '#guard':
                tr.guard = self.tokens[i + 1][1:-1].strip()
                self.check_valid_method_name(tr.guard)
            elif self.tokens[i] == '#uml_action':
                tr.action = self.tokens[i + 1][1:].strip()
                self.check_valid_method_name(tr.action)
            elif self.tokens[i] == '#std_action':
                tr.action = self.tokens[i + 1][6:].strip()
                self.check_valid_method_name(tr.action)

            if as_state and (tr.origin == tr.destination):
                if tr.action == '':
                    tr.action = '// Dummy action\n'
                    tr.action += '#warning "no reaction to event ' + tr.event.name
                    tr.action += ' for internal transition ' + tr.origin + ' -> '
                    tr.action += tr.origin + '"\n'

        self.current.add_transition(tr)
        self.tokens = []

    def parse_state(self, inst):
        """Parse one state action node and update state metadata or synthetic self-transition."""
        what = inst.data[6:]
        name = inst.children[0].upper()
        self.current.add_state(name)
        state = self.current.graph.nodes[name]['data']
        if what in ['entry', 'entering']:
            state.entering += inst.children[1].children[0][1:].strip() + ';\n'
        elif what in ['exit', 'leaving']:
            state.leaving += inst.children[1].children[0][1:].strip() + ';\n'
        elif what == 'comment':
            state.comment += inst.children[1].children[0][1:].strip()
        elif what in ['do', 'activity']:
            state.activity += inst.children[1].children[0][1:].strip()
        elif what in ['on', 'event']:
            self.tokens = [name, '->', name]
            for i in range(1, len(inst.children)):
                self.tokens.append('#' + str(inst.children[i].data))
                if inst.children[i].data != 'event':
                    self.tokens.append(str(inst.children[i].children[0]))
                else:
                    self.tokens.append(str(len(inst.children[i].children)))
                    for j in inst.children[i].children:
                        self.tokens.append(str(j))
            self.parse_transition(True)
        else:
            self.fatal('Bad syntax describing a state. Unkown token "' + inst.data + '"')

    def parse_extra_code(self, token, code):
        """Route custom '[header]/[code]/[test]/...' snippets into the right output bucket."""
        if token == '[brief]':
            if self.current.extra_code.brief != '':
                self.current.extra_code.brief += '\n//! '
            self.current.extra_code.brief += code
        elif token == '[header]':
            self.current.extra_code.header += code
            self.current.extra_code.header += '\n'
        elif token == '[footer]':
            self.current.extra_code.footer += code
            self.current.extra_code.footer += '\n'
        elif token == '[param]':
            if self.current.extra_code.argvs != '':
                self.current.extra_code.argvs += ', '
            self.current.extra_code.argvs += code
        elif token == '[cons]':
            self.current.extra_code.cons += '\n        , '
            self.current.extra_code.cons += code
        elif token == '[init]':
            self.current.extra_code.init += '        '
            self.current.extra_code.init += code
            self.current.extra_code.init += '\n'
        elif token == '[code]':
            if code not in ['public:', 'protected:', 'private:']:
                self.current.extra_code.code += '    '
            self.current.extra_code.code += code
            self.current.extra_code.code += '\n'
        elif token == '[test]':
            self.current.extra_code.unit_tests += code
            self.current.extra_code.unit_tests += '\n'
        else:
            self.fatal('Token ' + token + ' not yet managed')

    def visit_ast(self, inst):
        """Visit one AST node recursively and populate the in-memory StateMachine model."""
        if inst.data == 'cpp':
            self.parse_extra_code(str(inst.children[0]), inst.children[1].strip())
        elif inst.data == 'transition':
            self.tokens = [str(inst.children[0]), str(inst.children[1]), str(inst.children[2])]
            for i in range(3, len(inst.children)):
                self.tokens.append('#' + str(inst.children[i].data))
                if inst.children[i].data != 'event':
                    self.tokens.append(str(inst.children[i].children[0]))
                else:
                    self.tokens.append(str(len(inst.children[i].children)))
                    for j in inst.children[i].children:
                        self.tokens.append(str(j))
            self.parse_transition(False)
        elif inst.data == 'state_block':
            backup_fsm = self.current
            self.current = StateMachine()
            self.current.name = str(inst.children[0])
            self.current.class_name = self.fmt_name('Nested' + self.current.name)
            self.current.enum_name = self.current.class_name + self.enum_suffix()
            self.machines[self.current.name] = self.current
            self.current.parent = backup_fsm
            backup_fsm.children.append(self.current)
            for c in inst.children[1:]:
                self.visit_ast(c)
            self.current = backup_fsm
        elif inst.data[0:6] == 'state_':
            self.parse_state(inst)
        elif inst.data in ['comment', 'skin', 'hide']:
            return
        else:
            self.fatal('Token ' + inst.data + ' not yet managed. Please open a GitHub ticket to manage it')
