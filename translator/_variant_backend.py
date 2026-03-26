    ###########################################################################
    ### C++20 std::variant / std::visit backend helpers
    ###########################################################################

    def variant_real_states(self):
        """Return graph nodes that are real states (excluding [*] and *)."""
        return [s for s in self.current.graph.nodes if s not in ('[*]', '*')]

    def variant_first_real_state(self):
        """Return first real state for variant default-initialization."""
        for s in self.current.graph.nodes:
            if s not in ('[*]', '*'):
                return s
        return None

    def states_with_noevents(self):
        """Return real states that have at least one no-event outgoing transition."""
        result = []
        for state in self.current.graph.nodes:
            if state in ('[*]', '*'):
                continue
            for dest in self.current.graph.neighbors(state):
                tr = self.current.graph[state][dest]['data']
                if tr.event.name == '':
                    if state not in result:
                        result.append(state)
                    break
        return result

    ###########################################################################
    ### Variant backend: header include block.
    ###########################################################################
    def generate_variant_header(self, hpp):
        self.generate_common_header()
        if hpp:
            guard = self.current.class_name.upper() + '_HPP'
            self.fd.write('#ifndef ' + guard + '\n')
            self.fd.write('#  define ' + guard + '\n\n')
        self.fd.write('#  include "state_machine_variant.hpp"\n\n')
        if self.current.extra_code.header != '':
            self.fd.write(self.current.extra_code.header + '\n')

    ###########################################################################
    ### Variant backend: one empty struct per state + using alias.
    ###########################################################################
    def generate_variant_state_types(self):
        self.generate_function_comment('State types for ' + self.current.class_name + '.')
        for state in self.variant_real_states():
            comment = self.current.graph.nodes[state]['data'].comment
            self.fd.write('struct ' + self.state_name(state) + ' {}')
            if comment:
                self.fd.write('; //!< ' + comment + '\n')
            else:
                self.fd.write(';\n')
        self.fd.write('\n')
        type_alias = self.current.class_name + 'State'
        self.fd.write('using ' + type_alias + ' = std::variant<\n')
        real = self.variant_real_states()
        for i, state in enumerate(real):
            sep = '' if i == len(real) - 1 else ','
            self.indent(1), self.fd.write(self.state_name(state) + sep + '\n')
        self.fd.write('>;\n\n')

    ###########################################################################
    ### Variant backend: stringify via std::visit.
    ###########################################################################
    def generate_variant_stringify_function(self):
        type_alias = self.current.class_name + 'State'
        self.generate_function_comment('Convert state variant to human-readable string.')
        self.fd.write('static inline const char* stringify(' + type_alias + ' const& state)\n{\n')
        self.indent(1), self.fd.write('return std::visit(fsm::overloaded{\n')
        for state in self.variant_real_states():
            self.indent(2), self.fd.write('[](')
            self.fd.write(self.state_name(state) + ' const&)')
            self.fd.write(' { return "' + state + '"; },\n')
        self.indent(1), self.fd.write('}, state);\n')
        self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: code for initial transitions from [*].
    ### Used in both the constructor and enter().
    ###########################################################################
    def generate_variant_initial_transition_code(self, indent_level):
        if '[*]' not in self.current.graph.nodes:
            return
        for dest in list(self.current.graph.neighbors('[*]')):
            tr = self.current.graph['[*]'][dest]['data']
            if dest == '*':
                continue
            if tr.guard != '':
                self.indent(indent_level)
                self.fd.write('if (' + self.guard_function('[*]', dest) + '())\n')
                self.indent(indent_level), self.fd.write('{\n')
                if tr.action != '':
                    self.indent(indent_level + 1)
                    self.fd.write(self.transition_function('[*]', dest) + '();\n')
                self.indent(indent_level + 1)
                self.fd.write('m_state = ' + self.state_name(dest) + '{};\n')
                self.indent(indent_level + 1)
                self.fd.write('enterState_(m_state);\n')
                self.indent(indent_level + 1)
                self.fd.write('runInternalTransitions_();\n')
                self.indent(indent_level + 1)
                self.fd.write('return;\n')
                self.indent(indent_level), self.fd.write('}\n')
            else:
                # Unconditional initial transition
                if tr.action != '':
                    self.indent(indent_level)
                    self.fd.write(self.transition_function('[*]', dest) + '();\n')
                self.indent(indent_level)
                self.fd.write('m_state = ' + self.state_name(dest) + '{};\n')
                self.indent(indent_level)
                self.fd.write('enterState_(m_state);\n')
                self.indent(indent_level)
                self.fd.write('runInternalTransitions_();\n')
                break  # Only one unconditional transition is valid

    ###########################################################################
    ### Variant backend: constructor.
    ###########################################################################
    def generate_variant_constructor_method(self):
        self.generate_method_comment('Constructor. Evaluates initial guards and enters the first state.')
        self.indent(1)
        self.fd.write(self.current.class_name + '(' + self.current.extra_code.argvs + ')\n')
        cons = self.current.extra_code.cons.strip()
        if cons:
            self.indent(2), self.fd.write(': ' + cons + '\n')
        self.indent(1), self.fd.write('{\n')
        if self.current.extra_code.init != '':
            self.indent(2), self.fd.write('// User init code\n')
            self.fd.write(self.current.extra_code.init)
        self.generate_variant_initial_transition_code(2)
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: enter() resets the FSM to its initial state.
    ###########################################################################
    def generate_variant_enter_method(self):
        self.generate_method_comment('Activate (or re-activate) the state machine from its initial state.')
        self.indent(1), self.fd.write('void enter()\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('m_active = true;\n')
        if self.current.extra_code.init != '':
            self.indent(2), self.fd.write('// User init code\n')
            self.fd.write(self.current.extra_code.init)
        self.generate_variant_initial_transition_code(2)
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: exit() deactivates the FSM.
    ###########################################################################
    def generate_variant_exit_method(self):
        self.generate_method_comment('Deactivate the state machine.')
        self.indent(1), self.fd.write('void exit()\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('m_active = false;\n')
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: guards and transition actions (same naming, no MOCKABLE).
    ###########################################################################
    def generate_variant_transition_methods(self):
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.generate_method_comment(
                    'Guard: transition from ' + origin + ' to ' + destination + '.')
                self.indent(1)
                self.fd.write('bool ' + self.guard_function(origin, destination) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('const bool guard = (' + tr.guard + ');\n')
                self.indent(2), self.fd.write('FSM_LOG("[' + self.current.class_name.upper())
                self.fd.write('][GUARD ' + origin + ' --> ' + destination + ': ')
                self.fd.write(tr.guard + '] result: %s\\n",\n')
                self.indent(3), self.fd.write('guard ? "true" : "false");\n')
                self.indent(2), self.fd.write('return guard;\n')
                self.indent(1), self.fd.write('}\n\n')
            if tr.action != '':
                self.generate_method_comment(
                    'Transition action: ' + origin + ' --> ' + destination + '.')
                self.indent(1)
                self.fd.write('void ' + self.transition_function(origin, destination) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOG("[' + self.current.class_name.upper())
                self.fd.write('][TRANSITION ' + origin + ' --> ' + destination)
                if tr.action[:2] != '//':
                    self.fd.write(': ' + tr.action + ']\\n");\n')
                else:
                    self.fd.write(']\\n");\n')
                self.indent(2), self.fd.write(tr.action + ';\n')
                self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: entering/leaving state methods (no MOCKABLE).
    ###########################################################################
    def generate_variant_state_methods(self):
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.generate_method_comment('Entry action for state ' + state.name + '.')
                self.indent(1)
                self.fd.write('void ' + self.state_entering_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOG("[' + self.current.class_name.upper())
                self.fd.write('][ENTERING ' + state.name + ']\\n");\n')
                self.fd.write(state.entering)
                self.indent(1), self.fd.write('}\n\n')
            if state.leaving != '':
                self.generate_method_comment('Exit action for state ' + state.name + '.')
                self.indent(1)
                self.fd.write('void ' + self.state_leaving_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOG("[' + self.current.class_name.upper())
                self.fd.write('][LEAVING ' + state.name + ']\\n");\n')
                self.fd.write(state.leaving)
                self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: external event methods using std::visit dispatch.
    ### Semantics (matching StateMachine::transition()):
    ###   state change (origin != destination):
    ###     exitState_  -> guard -> action -> set m_state -> enterState_ -> runInternal
    ###   self-loop / "State : on event" (origin == destination):
    ###     guard -> action only (no exit/enter/runInternal)
    ###########################################################################
    def generate_variant_event_methods(self):
        for (sm, e) in self.current.broadcasts:
            self.generate_method_comment('Broadcast external event.')
            self.indent(1), self.fd.write('inline '), self.fd.write(e.header())
            self.fd.write(' { ' + self.child_machine_instance(sm) + '.' + e.caller() + '; }\n\n')
        for event, arcs in self.current.lookup_events.items():
            if event.name == '':
                continue
            self.generate_method_comment('External event: ' + event.name + '.')
            self.indent(1), self.fd.write(event.header() + '\n')
            self.indent(1), self.fd.write('{\n')
            self.indent(2), self.fd.write('FSM_LOG("[' + self.current.class_name.upper())
            self.fd.write('][EVENT %s]\\n", __func__);\n')
            for arg in event.params:
                self.fd.write('\n'), self.indent(2)
                self.fd.write(arg + ' = ' + arg + '_;\n')
            self.fd.write('\n')
            self.indent(2), self.fd.write('std::visit(fsm::overloaded{\n')
            for origin, destination in arcs:
                tr = self.current.graph[origin][destination]['data']
                is_self = (origin == destination)
                self.indent(3), self.fd.write('[this](' + self.state_name(origin) + '&)\n')
                self.indent(3), self.fd.write('{\n')
                if tr.guard != '':
                    self.indent(4), self.fd.write('if (!' + self.guard_function(origin, destination) + '()) return;\n')
                if is_self:
                    if tr.action != '':
                        self.indent(4), self.fd.write(self.transition_function(origin, destination) + '();\n')
                else:
                    self.indent(4), self.fd.write('exitState_(m_state);\n')
                    if tr.action != '':
                        self.indent(4), self.fd.write(self.transition_function(origin, destination) + '();\n')
                    self.indent(4), self.fd.write('m_state = ' + self.state_name(destination) + '{};\n')
                    self.indent(4), self.fd.write('enterState_(m_state);\n')
                    self.indent(4), self.fd.write('runInternalTransitions_();\n')
                self.indent(3), self.fd.write('},\n')
            self.indent(3), self.fd.write('[](auto&) {} // Ignore\n')
            self.indent(2), self.fd.write('}, m_state);\n')
            self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: enterState_ helper dispatches entry actions.
    ###########################################################################
    def generate_variant_enter_state_helper(self):
        type_alias = self.current.class_name + 'State'
        self.generate_method_comment('Dispatch entry action for the newly active state.')
        self.indent(1), self.fd.write('void enterState_(' + type_alias + ' const& s)\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('std::visit(fsm::overloaded{\n')
        for node in self.variant_real_states():
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.indent(3), self.fd.write('[this](' + self.state_name(node) + ' const&) {')
                self.fd.write(' ' + self.state_entering_function(node, False) + '(); },\n')
        self.indent(3), self.fd.write('[](auto const&) {}\n')
        self.indent(2), self.fd.write('}, s);\n')
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: exitState_ helper dispatches exit actions.
    ###########################################################################
    def generate_variant_exit_state_helper(self):
        type_alias = self.current.class_name + 'State'
        self.generate_method_comment('Dispatch exit action for the currently active state.')
        self.indent(1), self.fd.write('void exitState_(' + type_alias + ' const& s)\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('std::visit(fsm::overloaded{\n')
        for node in self.variant_real_states():
            state = self.current.graph.nodes[node]['data']
            if state.leaving != '':
                self.indent(3), self.fd.write('[this](' + self.state_name(node) + ' const&) {')
                self.fd.write(' ' + self.state_leaving_function(node, False) + '(); },\n')
        self.indent(3), self.fd.write('[](auto const&) {}\n')
        self.indent(2), self.fd.write('}, s);\n')
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: runInternalTransitions_ drives automatic transitions.
    ###########################################################################
    def generate_variant_internal_transitions(self):
        self.generate_method_comment('Execute automatic (no-event) transitions until stable.')
        self.indent(1), self.fd.write('void runInternalTransitions_()\n')
        self.indent(1), self.fd.write('{\n')
        noev_states = self.states_with_noevents()
        if not noev_states:
            self.indent(1), self.fd.write('}\n\n')
            return
        self.indent(2), self.fd.write('bool changed = true;\n')
        self.indent(2), self.fd.write('while (changed)\n')
        self.indent(2), self.fd.write('{\n')
        self.indent(3), self.fd.write('changed = false;\n')
        self.indent(3), self.fd.write('std::visit(fsm::overloaded{\n')
        for state in noev_states:
            self.indent(4), self.fd.write('[this, &changed](' + self.state_name(state) + '&)\n')
            self.indent(4), self.fd.write('{\n')
            for dest in list(self.current.graph.neighbors(state)):
                tr = self.current.graph[state][dest]['data']
                if tr.event.name != '':
                    continue
                if tr.guard != '':
                    self.indent(5), self.fd.write('if (' + self.guard_function(state, dest) + '())\n')
                    self.indent(5), self.fd.write('{\n')
                    self.indent(6), self.fd.write('exitState_(m_state);\n')
                    if tr.action != '':
                        self.indent(6), self.fd.write(self.transition_function(state, dest) + '();\n')
                    self.indent(6), self.fd.write('m_state = ' + self.state_name(dest) + '{};\n')
                    self.indent(6), self.fd.write('enterState_(m_state);\n')
                    self.indent(6), self.fd.write('changed = true;\n')
                    self.indent(6), self.fd.write('return;\n')
                    self.indent(5), self.fd.write('}\n')
                else:
                    self.indent(5), self.fd.write('exitState_(m_state);\n')
                    if tr.action != '':
                        self.indent(5), self.fd.write(self.transition_function(state, dest) + '();\n')
                    self.indent(5), self.fd.write('m_state = ' + self.state_name(dest) + '{};\n')
                    self.indent(5), self.fd.write('enterState_(m_state);\n')
                    self.indent(5), self.fd.write('changed = true;\n')
                    self.indent(5), self.fd.write('return;\n')
            self.indent(4), self.fd.write('},\n')
        self.indent(4), self.fd.write('[](auto&) {}\n')
        self.indent(3), self.fd.write('}, m_state);\n')
        self.indent(2), self.fd.write('}\n')
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: assemble the complete state machine class.
    ###########################################################################
    def generate_variant_state_machine_class(self):
        type_alias = self.current.class_name + 'State'
        self.generate_class_comment()
        self.fd.write('class ' + self.current.class_name + '\n{\npublic:\n\n')
        self.generate_variant_constructor_method()
        self.fd.write('#if defined(MOCKABLE)\n')
        self.generate_method_comment('Virtual destructor for test subclassing.')
        self.indent(1), self.fd.write('virtual ~' + self.current.class_name + '() = default;\n')
        self.fd.write('#endif\n\n')
        self.generate_variant_enter_method()
        self.generate_variant_exit_method()
        self.generate_method_comment('Return true when the state machine is active.')
        self.indent(1), self.fd.write('bool isActive() const { return m_active; }\n\n')
        self.generate_method_comment('Return the current state variant (read-only).')
        self.indent(1), self.fd.write(type_alias + ' const& state() const { return m_state; }\n\n')
        self.generate_method_comment('Return the current state as a human-readable string.')
        self.indent(1), self.fd.write('const char* c_str() const\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('return m_active ? stringify(m_state) : "--";\n')
        self.indent(1), self.fd.write('}\n\n')
        self.fd.write('public: // External events\n\n')
        self.generate_variant_event_methods()
        self.fd.write('private: // Guards and transition actions\n\n')
        self.generate_variant_transition_methods()
        self.fd.write('private: // State entry/exit actions\n\n')
        self.generate_variant_state_methods()
        self.fd.write('private: // Internal helpers\n\n')
        self.generate_variant_enter_state_helper()
        self.generate_variant_exit_state_helper()
        self.generate_variant_internal_transitions()
        self.fd.write('private: // Member variables\n\n')
        for event, arcs in self.current.lookup_events.items():
            for arg in event.params:
                self.indent(1), self.fd.write('//! \\brief Parameter for event ' + event.name + '\n')
                self.indent(1), self.fd.write(arg.upper() + ' ' + arg + ';\n')
        self.fd.write('\n')
        self.fd.write(self.current.extra_code.code)
        self.indent(1), self.fd.write('bool m_active = true;\n')
        first = self.variant_first_real_state()
        self.indent(1), self.fd.write(type_alias + ' m_state{ ')
        self.fd.write((self.state_name(first) + '{}' if first else '{}') + ' };\n')
        self.fd.write('};\n\n')

    ###########################################################################
    ### Variant backend: test file header (no gMock, no MOCKABLE define).
    ###########################################################################
    def generate_variant_unit_tests_header(self):
        self.generate_common_header()
        self.fd.write('#include "' + self.current.class_name + '.hpp"\n')
        self.fd.write('#include <gtest/gtest.h>\n')
        self.fd.write('#include <variant>\n')
        self.fd.write('#include <cstring>\n\n')

    ###########################################################################
    ### Variant backend: initial state test.
    ###########################################################################
    def generate_variant_unit_tests_assertions_initial_state(self):
        init_state = self.current.initial_state
        if init_state == '' or init_state not in self.current.graph.nodes:
            return
        possible = [d for d in self.current.graph.neighbors(init_state) if d != '*']
        if not possible:
            return
        self.indent(1), self.fd.write(self.current.class_name + ' fsm')
        if self.current.extra_code.argvs != '':
            self.fd.write('; // NOTE: adjust constructor arguments as needed\n')
        else:
            self.fd.write(';\n')
        if len(possible) == 1:
            s = possible[0]
            self.indent(1), self.fd.write('ASSERT_TRUE(std::holds_alternative<')
            self.fd.write(self.state_name(s) + '>(fsm.state()));\n')
            self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + s + '");\n')
        else:
            parts = ['std::holds_alternative<' + self.state_name(s) + '>(fsm.state())'
                     for s in possible]
            self.indent(1), self.fd.write('ASSERT_TRUE(' + '\n              || '.join(parts) + ');\n')

    def generate_variant_unit_tests_check_initial_state(self):
        self.generate_line_separator(0, ' ', 80, '-')
        self.fd.write('TEST(' + self.current.class_name + 'Tests, TestInitialState)\n{\n')
        self.indent(1), self.fd.write('FSM_LOG("===============================================\\n");\n')
        self.indent(1), self.fd.write('FSM_LOG("Check initial state after construction.\\n");\n')
        self.indent(1), self.fd.write('FSM_LOG("===============================================\\n");\n')
        self.generate_variant_unit_tests_assertions_initial_state()
        self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: cycle tests.
    ###########################################################################
    def generate_variant_unit_tests_check_cycles(self):
        count = 0
        for cycle in self.current.graph_cycles():
            self.generate_line_separator(0, ' ', 80, '-')
            self.fd.write('TEST(' + self.current.class_name + 'Tests, TestCycle' + str(count) + ')\n{\n')
            count += 1
            self.indent(1), self.fd.write('FSM_LOG("===========================================\\n");\n')
            self.indent(1), self.fd.write('FSM_LOG("Check cycle: [*]')
            for c in cycle:
                self.fd.write(' ' + c)
            self.fd.write('\\n");\n')
            self.indent(1), self.fd.write('FSM_LOG("===========================================\\n");\n')
            self.indent(1), self.fd.write(self.current.class_name + ' fsm')
            guard = self.current.graph[self.current.initial_state][cycle[0]]['data'].guard
            if self.current.extra_code.argvs != '':
                comment = '  // If ' + guard if guard else ''
                self.fd.write('; // NOTE: adjust constructor args' + comment + '\n')
            else:
                self.fd.write(';\n')
            self.indent(1), self.fd.write('ASSERT_TRUE(std::holds_alternative<')
            self.fd.write(self.state_name(cycle[0]) + '>(fsm.state()));\n')
            self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[0] + '");\n')
            for i in range(len(cycle) - 1):
                tr = self.current.graph[cycle[i]][cycle[i + 1]]['data']
                if tr.event.name != '':
                    self.fd.write('\n'), self.indent(1)
                    self.fd.write('FSM_LOG("\\n[' + self.current.class_name.upper())
                    self.fd.write('] Event ' + tr.event.name)
                    if tr.guard:
                        self.fd.write(' [' + tr.guard + ']')
                    self.fd.write(': ' + cycle[i] + ' ==> ' + cycle[i + 1] + '\\n");\n')
                    self.indent(1), self.fd.write('fsm.' + tr.event.caller() + ';\n')
                if i == len(cycle) - 2:
                    if self.current.graph[cycle[i + 1]][cycle[1]]['data'].event.name != '':
                        self.indent(1), self.fd.write('ASSERT_TRUE(std::holds_alternative<')
                        self.fd.write(self.state_name(cycle[i + 1]) + '>(fsm.state()));\n')
                        self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i + 1] + '");\n')
                elif self.current.graph[cycle[i + 1]][cycle[i + 2]]['data'].event.name != '':
                    self.indent(1), self.fd.write('ASSERT_TRUE(std::holds_alternative<')
                    self.fd.write(self.state_name(cycle[i + 1]) + '>(fsm.state()));\n')
                    self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i + 1] + '");\n')
            self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: path-to-sink tests.
    ###########################################################################
    def generate_variant_unit_tests_pathes_to_sinks(self):
        count = 0
        for path in self.current.graph_all_paths_to_sinks():
            self.generate_line_separator(0, ' ', 80, '-')
            self.fd.write('TEST(' + self.current.class_name + 'Tests, TestPath' + str(count) + ')\n{\n')
            count += 1
            self.indent(1), self.fd.write('FSM_LOG("===========================================\\n");\n')
            self.indent(1), self.fd.write('FSM_LOG("Check path:')
            for c in path:
                self.fd.write(' ' + c)
            self.fd.write('\\n");\n')
            self.indent(1), self.fd.write('FSM_LOG("===========================================\\n");\n')
            self.indent(1), self.fd.write(self.current.class_name + ' fsm')
            guard = (self.current.graph[path[0]][path[1]]['data'].guard
                     if len(path) > 1 else '')
            if self.current.extra_code.argvs != '':
                comment = '  // If ' + guard if guard else ''
                self.fd.write('; // NOTE: adjust constructor args' + comment + '\n')
            else:
                self.fd.write(';\n')
            for i in range(len(path) - 1):
                event = self.current.graph[path[i]][path[i + 1]]['data'].event
                if event.name != '':
                    guard2 = self.current.graph[path[i]][path[i + 1]]['data'].guard
                    self.fd.write('\n'), self.indent(1)
                    self.fd.write('FSM_LOG("[' + self.current.class_name.upper())
                    self.fd.write('] Event ' + event.name)
                    if guard2:
                        self.fd.write(' [' + guard2 + ']')
                    self.fd.write(': ' + path[i] + ' ==> ' + path[i + 1] + '\\n");\n')
                    self.indent(1), self.fd.write('fsm.' + event.caller() + ';\n')
                if i == len(path) - 2:
                    self.indent(1), self.fd.write('ASSERT_TRUE(std::holds_alternative<')
                    self.fd.write(self.state_name(path[i + 1]) + '>(fsm.state()));\n')
                    self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + path[i + 1] + '");\n')
                elif self.current.graph[path[i + 1]][path[i + 2]]['data'].event.name != '':
                    self.indent(1), self.fd.write('ASSERT_TRUE(std::holds_alternative<')
                    self.fd.write(self.state_name(path[i + 1]) + '>(fsm.state()));\n')
                    self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + path[i + 1] + '");\n')
            self.fd.write('}\n\n')

    ###########################################################################
    ### Variant backend: top-level unit test file generator.
    ###########################################################################
    def generate_variant_unit_tests(self, cxxfile, files, separated):
        filename = self.current.class_name + 'Tests.cpp'
        self.fd = open(os.path.join(os.path.dirname(cxxfile), filename), 'w')
        self.generate_variant_unit_tests_header()
        self.generate_variant_unit_tests_check_initial_state()
        self.generate_variant_unit_tests_check_cycles()
        self.generate_variant_unit_tests_pathes_to_sinks()
        if not separated:
            self.generate_unit_tests_main_function(filename, files)
        self.fd.close()

    ###########################################################################
    ### Variant backend: generate the FSM header/source file.
    ###########################################################################
    def generate_variant_state_machine(self, cxxfile):
        hpp = self.is_hpp_file(cxxfile)
        self.fd = open(cxxfile, 'w')
        self.generate_variant_header(hpp)
        self.generate_variant_state_types()
        self.generate_variant_stringify_function()
        self.generate_variant_state_machine_class()
        self.generate_footer(hpp)
        self.fd.close()

    ###########################################################################
    ### Variant backend: entry point — generates all FSM and test files.
    ###########################################################################
    def generate_cxx_variant_code(self, cxxfile, separated):
        files = []
        for self.current in self.machines.values():
            f = self.current.class_name + 'Tests.cpp'
            files.append(f)
            # cxxfile is 'hpp20' or 'cpp20'; the real extension is hpp or cpp
            real_ext = 'hpp' if 'hpp' in cxxfile else 'cpp'
            outfile = self.current.class_name + '.' + real_ext
            self.generate_variant_state_machine(outfile)
            self.generate_variant_unit_tests(outfile, files, separated)
        if separated:
            mainfile = self.master.class_name + 'MainTests.cpp'
            mainfile = os.path.join(os.path.dirname(cxxfile), mainfile)
            self.generate_unit_tests_main_file(mainfile, files)
