#!/usr/bin/env python3
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
## Note: in this document the term state machine, FSM, HSM or statecharts are
## equivalent.
###############################################################################

from pathlib import Path
from lark import Lark, Transformer

import sys, os, re, itertools
import shutil
import subprocess
try:
    from .naming import camel_to_snake, CPP_RESERVED_IDENTIFIERS
    from .model import Event, Transition, StateMachine
    from .parsing import ParsingMixin
    from .generators import generate_cpp11_backend, generate_cpp20_backend
    from .generators.io_helpers import emit_to_file
except ImportError:
    from naming import camel_to_snake, CPP_RESERVED_IDENTIFIERS
    from model import Event, Transition, StateMachine
    from parsing import ParsingMixin
    from generators import generate_cpp11_backend, generate_cpp20_backend
    from generators.io_helpers import emit_to_file


###############################################################################
### Console color for print.
###############################################################################
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

###############################################################################
### Context of the parser translating a PlantUML file depicting a state machine
### into a C++ file state machine holding some unit tests.
### See https://plantuml.com/fr/state-diagram
###############################################################################
class Parser(ParsingMixin, object):
    """Main translator orchestrator.

    Parsing and AST normalization are provided by `ParsingMixin`, while this
    class keeps generation, naming, formatting, and output orchestration.
    """

    def __init__(self):
        # Context-free language parser (Lark lib)
        self.parser = None
        # Abstract Syntax Tree (Lark lib)
        self.ast = None
        # List of tokens split from the AST (ugly hack !!!).
        self.tokens = []
        # File descriptor of the opened file (plantUML, generated files).
        self.fd = None
        # Name of the plantUML file (input of the tool).
        self.uml_file = ''
        # Currently active state machine (used as side effect instead of
        # passing the current FSM as argument to functions. Ok maybe consider
        # as dirty but doing like this in OpenGL)
        self.current = StateMachine()
        # Master state machine (entry point).
        self.master = StateMachine()
        # Dictionnary of all state machines (master and nested).
        self.machines = dict() # type: StateMachine()
        # Output directory for generated artifacts.
        self.output_dir = '.'
        # Naming convention: snake_case by default.
        self.snake_case = True
        # Optional C++ namespace for generated code.
        self.namespace = ''
        # Code-generation mode for variant backend.
        self.gen_mode = 'inline'
        # Generation-time thread-safety switch.
        self.thread_safe = False
        # Indentation used for method comment separators.
        self.method_comment_indent = 4

    ###########################################################################
    ### Is the generated file should be a C++ source file or header file ?
    ### param[in] file path of the file to be generated.
    ### return True if the file extension matches for a C++ header file.
    ###########################################################################
    def is_hpp_file(self, file):
        filename, extension = os.path.splitext(file)
        return True if extension in ['.h', '.hpp', '.hh', '.hxx'] else False

    ###########################################################################
    ### Print a general error message on the console and exit the application.
    ### param[in] msg the message to print.
    ###########################################################################
    def fatal(self, msg):
        print(f"{bcolors.FAIL}   FATAL in the state machine " + self.current.name + \
              ": " + msg + f"{bcolors.ENDC}")
        sys.exit(-1)

    ###########################################################################
    ### Generate a separator line for function.
    ### param[in] spaces the number of spaces char to print.
    ### param[in] the space character to print.
    ### param[in] count the number of character to print a line of comment.
    ### param[in] c the comment line character to print.
    ###########################################################################
    def generate_line_separator(self, spaces, s, count, c):
        self.fd.write(s * spaces)
        self.fd.write('//')
        self.fd.write(c * count)
        self.fd.write('\n')

    ###########################################################################
    ### Generate a function or a method comment with its text and lines as
    ### separtor. Comment separator follows the comment size (80 as min size).
    ### param[in] spaces the number of spaces char to print.
    ### param[in] the space character to print.
    ### param[in] comment the message in the comment.
    ### param[in] c the comment line character to print.
    ###########################################################################
    def generate_comment(self, spaces, s, comment, c):
        lines = comment.split('\n') if comment != '' else ['']
        self.fd.write(s * spaces)
        self.fd.write('/**\n')
        for index, line in enumerate(lines):
            self.fd.write(s * spaces)
            self.fd.write(' *')
            if index == 0:
                self.fd.write(' @brief')
                if line != '':
                    self.fd.write(' ' + line)
            elif line != '':
                self.fd.write(' ' + line)
            self.fd.write('\n')
        self.fd.write(s * spaces)
        self.fd.write(' */\n')

    ###########################################################################
    ### Generate function comment with its text.
    ###########################################################################
    def generate_function_comment(self, comment):
        self.generate_comment(0, ' ', comment, '*')

    ###########################################################################
    ### Code generator: add a dummy method comment.
    ###########################################################################
    def generate_method_comment(self, comment):
        self.generate_comment(self.method_comment_indent, ' ', comment, '-')

    ###########################################################################
    ### Identation.
    ### param[in] count the depth of indentation.
    ###########################################################################
    def indent(self, depth):
        self.fd.write(' ' * 4 * depth)

    def emit_indented_code(self, code, depth):
        """Emit non-empty lines of raw code with a target indentation depth."""
        if code == '':
            return
        for raw_line in code.splitlines():
            line = raw_line.strip()
            if line == '':
                continue
            self.indent(depth)
            self.fd.write(line + '\n')

    def fmt_name(self, name):
        """Apply naming convention and avoid reserved C++ identifiers."""
        candidate = camel_to_snake(name) if self.snake_case else name
        if candidate in CPP_RESERVED_IDENTIFIERS:
            return candidate + '_id'
        return candidate

    def enum_suffix(self):
        """Return enum type suffix according to the selected naming style."""
        return '_states' if self.snake_case else 'States'

    def mock_class_name(self):
        """Return generated mock class name used by unit-test output."""
        return ('mock_' + self.current.class_name) if self.snake_case else ('Mock' + self.current.class_name)

    def test_suite_name(self):
        """Return generated test suite name for the current state machine."""
        return self.current.class_name + ('_tests' if self.snake_case else 'Tests')

    def tests_file_suffix(self):
        """Return generated test file suffix based on naming convention."""
        return '_tests.cpp' if self.snake_case else 'Tests.cpp'

    def variant_state_alias(self):
        """Return helper alias name used by the C++20 variant backend."""
        return 'fsm_state' if self.snake_case else 'FsmState'

    def runtime_base_template_arguments(self):
        """Build template arguments for the runtime state_machine base type."""
        args = [self.current.class_name, self.current.enum_name]
        if self.thread_safe:
            args.append('true')
        return ', '.join(args)

    def runtime_base_class_name(self):
        """Return runtime base class symbol according to naming convention."""
        return 'state_machine' if self.snake_case else 'StateMachine'

    def runtime_base_class_qualified_name(self):
        """Return fully qualified runtime base class symbol."""
        return 'fsm::' + self.runtime_base_class_name()

    def runtime_transition_type(self):
        """Return runtime transition struct symbol according to naming convention."""
        return 'transition' if self.snake_case else 'Transition'

    def runtime_transitions_type(self):
        """Return runtime transitions container symbol according to naming convention."""
        return 'transitions' if self.snake_case else 'Transitions'

    def namespace_qualified(self, symbol):
        """Qualify a symbol with the configured namespace, if any."""
        if self.namespace == '':
            return symbol
        return '::' + self.namespace + '::' + symbol

    def test_class_name(self):
        """Return namespace-qualified generated class name for test code."""
        return self.namespace_qualified(self.current.class_name)

    def test_enum_name(self):
        """Return namespace-qualified generated enum name for test code."""
        return self.namespace_qualified(self.current.enum_name)

    def state_enum_for_tests(self, state):
        """Return fully qualified enum constant string for one state in tests."""
        return self.test_enum_name() + '::' + self.state_name(state)

    def method_stem(self, snake_name, camel_name):
        """Pick snake_case or CamelCase method stem based on configured naming."""
        return snake_name if self.snake_case else camel_name

    def active_method_name(self):
        """Return generated 'is active' query method name."""
        return self.method_stem('is_active', 'isActive')

    def _extract_bare_called_functions(self, code):
        """Extract simple callable identifiers from a code fragment.

        This is intentionally heuristic and used only for generating TODO stubs.
        """
        if code == '':
            return set()
        ignored = {
            'if', 'for', 'while', 'switch', 'return', 'sizeof',
            'static_cast', 'dynamic_cast', 'const_cast', 'reinterpret_cast',
            'FSM_LOGD', 'FSM_LOGE', 'FSM_LOG',
        }
        pattern = re.compile(r'(?<![\w:\.>])([A-Za-z_][A-Za-z0-9_]*)\s*\(')
        names = set()
        for name in pattern.findall(code):
            if name not in ignored:
                names.add(name)
        return names

    def _known_generated_method_names(self):
        """Collect callback/method names already generated by the translator."""
        names = {
            self.current.class_name,
            'enter',
            'exit',
            self.active_method_name(),
            'c_str',
            'is',
        }
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                names.add(self.guard_function(origin, destination, False))
            if tr.action != '':
                names.add(self.transition_function(origin, destination, False))
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                names.add(self.state_entering_function(node, False))
            if state.leaving != '':
                names.add(self.state_leaving_function(node, False))
            if state.internal != '' and node != '[*]':
                names.add(self.state_internal_function(node, False))
        for event, arcs in self.current.lookup_events.items():
            if event.name != '':
                names.add(event.name)
        return names

    def _missing_user_call_stubs(self):
        """Return unresolved callback names referenced by model code snippets."""
        called = set()
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            called |= self._extract_bare_called_functions(tr.action)
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            called |= self._extract_bare_called_functions(state.entering)
            called |= self._extract_bare_called_functions(state.leaving)
            called |= self._extract_bare_called_functions(state.internal)

        known = self._known_generated_method_names()
        declared_in_user_code = self._extract_bare_called_functions(self.current.extra_code.code)
        return sorted(called - known - declared_in_user_code)

    def emit_client_code_section(self):
        """Emit user-provided '[code]' snippets and fallback TODO callback stubs."""
        self.fd.write(self.current.extra_code.code)
        stubs = self._missing_user_call_stubs()
        if len(stubs) == 0:
            return
        self.fd.write('\n')
        self.indent(1), self.fd.write('// TODO: auto-generated stubs for unresolved user callbacks\n')
        self.indent(1), self.fd.write('// Replace or remove them by adding real methods in [code] blocks.\n')
        for name in stubs:
            self.indent(1), self.fd.write('template<typename... Args>\n')
            self.indent(1), self.fd.write('void ' + name + '(Args&&...)\n')
            self.indent(1), self.fd.write('{\n')
            self.indent(2), self.fd.write('// TODO: implement callback from PlantUML action/state code.\n')
            self.indent(1), self.fd.write('}\n')

    def generate_namespace_begin(self):
        """Emit opening namespace blocks for generated C++ output."""
        if self.namespace == '':
            return
        for ns in self.namespace.split('::'):
            self.fd.write('namespace ' + ns + ' {\n')
        self.fd.write('\n')

    def generate_namespace_end(self):
        """Emit closing namespace blocks matching `generate_namespace_begin`."""
        if self.namespace == '':
            return
        self.fd.write('\n')
        for ns in reversed(self.namespace.split('::')):
            self.fd.write('} // namespace ' + ns + '\n')

    ###########################################################################
    ### Generate #include "foo.h" or #include <foo.h>
    ###########################################################################
    def generate_include(self, indent, b, file, e):
        """Emit one C/C++ include directive using caller-provided delimiters."""
        self.fd.write('#include ' + b + file + e + '\n')

    ###########################################################################
    ### You can add here your copyright, license ...
    ###########################################################################
    def generate_common_header(self):
        """Emit the standard generated-file banner and legal disclaimer."""
        self.fd.write('// ############################################################################\n')
        self.fd.write('// This file has been generated by PlantUMLStatecharts_VariantFSM\n')
        self.fd.write('// from the PlantUML statechart ' + self.uml_file + '\n')
        self.fd.write('// This code generation is still experimental. Some border cases may not be\n')
        self.fd.write('// correctly managed!\n')
        self.fd.write('//\n')
        self.fd.write('// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n')
        self.fd.write('// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,\n')
        self.fd.write('// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE\n')
        self.fd.write('// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER\n')
        self.fd.write('// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,\n')
        self.fd.write('// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE\n')
        self.fd.write('// SOFTWARE.\n')
        self.fd.write('// ############################################################################\n\n')

    ###########################################################################
    ### Code generator: generate the header of the file.
    ### param[in] hpp set to True if generated file is a C++ header file.
    ###########################################################################
    def generate_header(self, hpp):
        """Emit generated file prologue, includes, warnings, and user header snippets."""
        indent = 1 if hpp else 0
        self.generate_common_header()
        if hpp:
            self.fd.write('#pragma once\n')
            self.fd.write('#ifndef ' + self.current.class_name.upper() + '_HPP\n')
            self.fd.write('#define ' + self.current.class_name.upper() + '_HPP\n\n')
        for sm in self.current.children:
            self.generate_include(indent, '"', sm.class_name + '.hpp', '"')
        if len(self.current.children) == 0:
            self.generate_include(indent, '"', 'state_machine.hpp', '"')
            self.fd.write('\n')
            self.generate_include(indent, '<', 'array', '>')
            self.generate_include(indent, '<', 'cassert', '>')
            self.generate_include(indent, '<', 'cstdlib', '>')
            self.generate_include(indent, '<', 'map', '>')
            self.generate_include(indent, '<', 'mutex', '>')
            self.generate_include(indent, '<', 'queue', '>')
            self.generate_include(indent, '<', 'cstdio', '>')
            self.fd.write('\n')
        for w in self.current.warnings:
            self.fd.write('\n#warning "' + w + '"\n')
        if hpp:
            self.fd.write('// Provide a default empty MOCKABLE for non-testing builds.\n')
            self.fd.write('#ifndef MOCKABLE\n')
            self.fd.write('#define MOCKABLE\n')
            self.fd.write('#endif\n')
        self.fd.write(self.current.extra_code.header)
        self.fd.write('\n')

    ###########################################################################
    ### Code generator: generate the footer of the file.
    ### param[in] hpp set to True if generated file is a C++ header file.
    ###########################################################################
    def generate_footer(self, hpp):
        """Emit user footer snippets and close the include guard for headers."""
        self.fd.write(self.current.extra_code.footer)
        if hpp:
            self.fd.write('#endif // ' + self.current.class_name.upper() + '_HPP')

    ###########################################################################
    ### Code generator: generate the states for the state machine as enums.
    ###########################################################################
    def generate_state_enums(self):
        """Emit the enum that lists client states plus mandatory internal states."""
        self.generate_function_comment('States of the state machine.')
        self.fd.write('enum class ' + self.current.enum_name + '\n{\n')
        self.indent(1), self.fd.write('// Client states:\n')
        for state in list(self.current.graph.nodes):
            self.indent(1), self.fd.write(self.state_name(state) + ',')
            comment = self.current.graph.nodes[state]['data'].comment
            if comment != '':
                self.fd.write(' /**< ' + comment + ' */')
            self.fd.write('\n')
        self.indent(1), self.fd.write('// Mandatory internal states:\n')
        self.indent(1), self.fd.write('IGNORING_EVENT, CANNOT_HAPPEN, MAX_STATES\n')
        self.fd.write('};\n\n')

    ###########################################################################
    ### Code generator: generate the function that stringify states.
    ###########################################################################
    def generate_stringify_function(self):
        """Emit inline helper that maps state enum values to string names."""
        self.generate_function_comment('Convert enum states to human readable string.')
        self.fd.write('static inline const char* stringify(' + self.current.enum_name + \
                      ' const state)\n{\n')
        self.indent(1), self.fd.write('static const char* s_states[] =\n')
        self.indent(1), self.fd.write('{\n')
        for state in list(self.current.graph.nodes):
            self.indent(2), self.fd.write('[int(' + self.state_enum(state) + ')] = "' + state + '",\n')
        self.indent(1), self.fd.write('};\n\n')
        self.indent(1), self.fd.write('return s_states[int(state)];\n};\n\n')

    ###########################################################################
    ### Convert the state name (raw PlantUML name to C++ name)
    ### param[in] state the PlantUML name of the state.
    ### return the C++ name.
    ###########################################################################
    def state_name(self, state):
        """Map raw PlantUML state names to generated C++ enum/member identifiers."""
        if state == '[*]':
            return self.fmt_name('CONSTRUCTOR')
        if state == '*':
            return self.fmt_name('DESTRUCTOR')
        return self.fmt_name(state)

    ###########################################################################
    ### Return the C++ enum for the given state.
    ### param[in] state the PlantUML name of the state.
    ###########################################################################
    def state_enum(self, state):
        """Return the fully qualified enum constant for a given state."""
        return self.current.enum_name + '::' + self.state_name(state)

    ###########################################################################
    ### Return the C++ method for transition guards.
    ### param[in] source the origin state (PlantUML name).
    ### param[in] destination the destination state (PlantUML name).
    ### param[in] class_name if True prepend the class name.
    ###########################################################################
    def guard_function(self, source, destination, class_name=False):
        """Return generated guard callback name for one transition."""
        s = self.current.class_name + '::' if class_name else ''
        return s + self.method_stem('on_guarding_', 'onGuarding_') + self.state_name(source) + '_' + self.state_name(destination)

    ###########################################################################
    ### Return the C++ method for transition actions.
    ### param[in] source the origin state (PlantUML name).
    ### param[in] destination the destination state (PlantUML name).
    ### param[in] class_name if True prepend the class name.
    ###########################################################################
    def transition_function(self, source, destination, class_name=False):
        """Return generated transition-action callback name for one transition."""
        s = self.current.class_name + '::' if class_name else ''
        return s + self.method_stem('on_transitioning_', 'onTransitioning_') + self.state_name(source) + '_' + self.state_name(destination)

    ###########################################################################
    ### Return the C++ method for entering state actions.
    ### param[in] state the PlantUML name of the state.
    ### param[in] entering if True for entering actions else for leaving action.
    ###########################################################################
    def state_entering_function(self, state, class_name=True):
        """Return generated state-entry callback name."""
        s = self.current.class_name + '::' if class_name else ''
        return s + self.method_stem('on_entering_', 'onEntering_') + self.state_name(state)

    ###########################################################################
    ### Return the C++ method for leaving state actions.
    ### param[in] state the PlantUML name of the state.
    ### param[in] entering if True for entering actions else for leaving action.
    ###########################################################################
    def state_leaving_function(self, state, class_name=True):
        """Return generated state-exit callback name."""
        s = self.current.class_name + '::' if class_name else ''
        return s + self.method_stem('on_leaving_', 'onLeaving_') + self.state_name(state)

    ###########################################################################
    ### Return the C++ method for internal state transition.
    ### param[in] state the PlantUML name of the state.
    ### param[in] entering if True for entering actions else for leaving action.
    ###########################################################################
    def state_internal_function(self, state, class_name=True):
        """Return generated internal no-event handler name for a state."""
        s = self.current.class_name + '::' if class_name else ''
        return s + self.method_stem('on_internal_', 'onInternal_') + self.state_name(state)

    ###########################################################################
    ### Return the C++ method for activity state.
    ### param[in] state the PlantUML name of the state.
    ### param[in] entering if True for entering actions else for leaving action.
    ###########################################################################
    def state_activity_function(self, state, class_name=True):
        """Return generated state-activity callback name."""
        s = self.current.class_name + '::' if class_name else ''
        return s + self.method_stem('on_activity_', 'onActivity_') + self.state_name(state)

    ###########################################################################
    ### Return the C++ variable memeber of the nested state machine.
    ### param[in] fsm the nested state machine.
    ###########################################################################
    def child_machine_instance(self, fsm):
        """Return member variable name used for a nested/generated child machine."""
        if isinstance(fsm, str):
            return 'm_nested_' + fsm.lower()
        return 'm_nested_' + fsm.name.lower()

    ###########################################################################
    ### Generate the PlantUML code from the graph.
    ###########################################################################
    def generate_plantuml_code(self, comm=''):
        """Render the interpreted in-memory graph back to PlantUML text."""
        code = ''
        for node in list(self.current.graph.nodes()):
            if node in ['[*]', '*']:
                continue
            state = self.current.graph.nodes[node]['data']
            if state.entering == '' and state.leaving == '' and state.activity == '':
                continue
            code += comm + str(state).replace('\n', '\n' + comm) + '\n'
        for src in list(self.current.graph.nodes()):
            for dest in list(self.current.graph.neighbors(src)):
                tr = self.current.graph[src][dest]['data']
                code += comm + str(tr) + '\n'
        return code

    ###########################################################################
    ### Generate the PlantUML file from the graph structure.
    ###########################################################################
    def generate_plantuml_file(self):
        """Write interpreted PlantUML snapshots for each generated machine."""
        for self.current in self.machines.values():
            filename = os.path.join(self.output_dir,
                                    self.current.name + '-interpreted.plantuml')
            self.fd = open(filename, 'w')
            self.fd.write('@startuml\n')
            self.fd.write(self.generate_plantuml_code())
            self.fd.write('@enduml\n')
            self.fd.close()

    ###########################################################################
    ### Generate the comment for the state machine class.
    ###########################################################################
    def generate_class_comment(self):
        """Emit class-level documentation, including embedded interpreted PlantUML."""
        if self.current.extra_code.brief != '':
            comment = self.current.extra_code.brief
        else:
            comment = 'State machine concrete implementation.'
        comment += '\n@startuml\n'
        comment += self.generate_plantuml_code()
        comment += '@enduml'
        self.generate_function_comment(comment)

    ###########################################################################
    ### Generate the table of states holding their entering or leaving actions.
    ### Note: the table may be empty (all states do not actions) in this case
    ### the table is not generated.
    ###########################################################################
    def generate_table_of_states(self, base_depth=2):
        """Emit sparse runtime state table entries with state callbacks."""
        for state in list(self.current.graph.nodes):
            s = self.current.graph.nodes[state]['data']
            # Nothing to do with initial state
            if (s.name == '[*]'):
                continue
            # Sparse notation: nullptr are implicit so skip generating them
            if s.entering == '' and s.leaving == '' and s.internal == '':
                continue
            self.indent(base_depth), self.fd.write('m_states[int(' + self.state_enum(s.name) + ')] =\n')
            self.indent(base_depth), self.fd.write('{\n')
            if s.leaving != '':
                self.indent(base_depth + 1), self.fd.write('.leaving = &')
                self.fd.write(self.state_leaving_function(state, True))
                self.fd.write(',\n')
            if s.entering != '':
                self.indent(base_depth + 1), self.fd.write('.entering = &')
                self.fd.write(self.state_entering_function(state, True))
                self.fd.write(',\n')
            if s.internal != '':
                self.indent(base_depth + 1), self.fd.write('.internal = &')
                self.fd.write(self.state_internal_function(state, True))
                self.fd.write(',\n')
            if s.activity != '':
                self.indent(base_depth + 1), self.fd.write('.activity = &')
                self.fd.write(self.state_activity_function(state, True))
                self.fd.write(',\n')
            self.indent(base_depth), self.fd.write('};\n')

    ###########################################################################
    ### Generate the code of the state machine constructor method.
    ### TODO missing generating ": m_foo(foo),\n" ...
    ###########################################################################
    def generate_constructor_method(self):
        """Emit constructor implementation for runtime initialization and user init code."""
        self.generate_method_comment('Default constructor. Start from initial '
                                     'state and call it actions.')
        self.indent(1)
        self.fd.write(self.current.class_name + '(' + self.current.extra_code.argvs + ')\n')
        self.indent(2), self.fd.write(': ' + self.runtime_base_class_name() + '(' + self.state_enum(self.current.initial_state) + ')')
        self.fd.write(self.current.extra_code.cons), self.fd.write('\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('// Init actions on states\n')
        self.generate_table_of_states()
        self.fd.write('\n'), self.indent(2), self.fd.write('// Init user code\n')
        self.fd.write(self.current.extra_code.init)
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Generate the code of the state machine destructor method.
    ###########################################################################
    def generate_destructor_method(self):
        """Emit destructor declaration/definition used by mock-enabled builds."""
        self.generate_method_comment('Needed because of virtual methods (define MOCKABLE=virtual to enable GMock).')
        self.indent(1)
        self.fd.write('MOCKABLE ~' + self.current.class_name + '() = default;\n\n')

    ###########################################################################
    ### Generate the state machine initial entering method.
    ###########################################################################
    def generate_enter_method(self):
        """Emit enter() implementation resetting runtime state and initial transition."""
        self.generate_method_comment('Reset the state machine and nested machines. Do the initial internal transition.')
        self.indent(1), self.fd.write('void enter()\n')
        self.indent(1), self.fd.write('{\n')
        # Init base class of the state machine
        self.indent(2), self.fd.write(self.runtime_base_class_name() + '::enter();\n')
        # Init nested state machines
        for sm in self.current.children:
            self.indent(2), self.fd.write(self.child_machine_instance(sm) + '.enter();\n')
        # User's init code
        if self.current.extra_code.init != '':
            self.fd.write('\n'), self.indent(2), self.fd.write('// Init user code\n')
            self.fd.write(self.current.extra_code.init)
        # Initial internal transition
        if self.current.graph.nodes['[*]']['data'].internal != '':
            self.fd.write('\n'), self.indent(2), self.fd.write('// Internal transition\n')
            self.fd.write(self.current.graph.nodes['[*]']['data'].internal)
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Generate the state machine exting method.
    ###########################################################################
    def generate_exit_method(self):
        """Emit exit() implementation resetting runtime state and nested machines."""
        self.generate_method_comment('Reset the state machine and nested machines. Do the initial internal transition.')
        self.indent(1), self.fd.write('void exit()\n')
        self.indent(1), self.fd.write('{\n')
        # Init base class of the state machine
        self.indent(2), self.fd.write(self.runtime_base_class_name() + '::exit();\n')
        # Init nested state machines
        for sm in self.current.children:
            self.indent(2), self.fd.write(self.child_machine_instance(sm) + '.exit();\n')
        self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Generate external events to the state machine (public methods).
#FIXME
# Manage the case of the transition goes or leaves a composite state
#            if len(self.machines[origin].children) != 0:
#                for sm in self.current.children:
#                    self.indent(2), self.fd.write(self.child_machine_instance(sm) + '.exit();\n')
#            elif len(self.machines[destination].children) != 0:
#                for sm in self.current.children:
#                    self.indent(2), self.fd.write(self.child_machine_instance(sm) + '.enter();\n')
#            # Generate the table of transitions
    ###########################################################################
    def generate_event_methods(self):
        """Emit public external-event methods and their transition dispatch tables."""
        # Broadcasr external events to nested state machine
        for (sm, e) in self.current.broadcasts:
            self.generate_method_comment('Broadcast external event.')
            self.indent(1), self.fd.write('inline '), self.fd.write(e.header())
            self.fd.write(' { ' + self.child_machine_instance(sm) + '.' + e.caller() + '; }\n\n')
        # React to external events
        for event, arcs in self.current.lookup_events.items():
            if event.name == '':
                continue
            self.generate_method_comment('External event.')
            self.indent(1), self.fd.write(event.header() + '\n')
            self.indent(1), self.fd.write('{\n')
            # Display data event
            self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][EVENT %s]')
            if len(event.params) != 0:
                self.fd.write(' with params XXX') # FIXME a finir
            self.fd.write('\\n", __func__);\n\n')
            # Copy data event
            for arg in event.params:
                self.indent(2), self.fd.write(arg + ' = ' + arg + '_;\n\n')
            # Table of transitions
            self.indent(2), self.fd.write('// State transition and actions\n')
            self.indent(2), self.fd.write('static const ' + self.runtime_transitions_type() + ' s_transitions =\n')
            self.indent(2), self.fd.write('{\n')
            for origin, destination in arcs:
                tr = self.current.graph[origin][destination]['data']
                self.indent(3), self.fd.write('{\n')
                self.indent(4), self.fd.write(self.state_enum(origin) + ',\n')
                self.indent(4), self.fd.write('{\n')
                self.indent(5), self.fd.write('.destination = ' + self.state_enum(destination) + ',\n')
                if tr.guard != '':
                    self.indent(5), self.fd.write('.guard = &' + self.guard_function(origin, destination, True) + ',\n')
                if tr.action != '':
                    self.indent(5), self.fd.write('.action = &' + self.transition_function(origin, destination, True) + ',\n')
                self.indent(4), self.fd.write('},\n')
                self.indent(3), self.fd.write('},\n')
            self.indent(2), self.fd.write('};\n\n')
            self.indent(2), self.fd.write('transition(s_transitions);\n')
            self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Generate guards and actions on transitions.
    ###########################################################################
    def generate_transition_methods(self):
        """Emit generated guard/action methods attached to graph transitions."""
        transitions = list(self.current.graph.edges)
        for origin, destination in transitions:
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.generate_method_comment('Guard the transition from state ' + origin  + ' to state ' + destination + '.')
                self.indent(1), self.fd.write('MOCKABLE bool ' + self.guard_function(origin, destination) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('const bool guard = (' + tr.guard + ');\n')
                self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][GUARD ' + origin + ' --> ' + destination + ': ' + tr.guard + '] result: %s\\n",\n')
                self.indent(3), self.fd.write('(guard ? "true" : "false"));\n')
                self.indent(2), self.fd.write('return guard;\n')
                self.indent(1), self.fd.write('}\n\n')
            if tr.action != '':
                self.generate_method_comment('Do the action when transitioning from state ' + origin + ' to state ' + destination + '.')
                self.indent(1), self.fd.write('MOCKABLE void ' + self.transition_function(origin, destination) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][TRANSITION ' + origin + ' --> ' + destination)
                if tr.action[0:2] != '//':
                    self.fd.write(': ' + tr.action + ']\\n");\n')
                else: # Cannot display action since contains comment + warnings
                    self.fd.write(']\\n");\n')
                self.indent(2), self.fd.write(tr.action + ';\n')
                self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Generate leaving and entering actions associated to states.
    ###########################################################################
    def generate_state_methods(self):
        """Emit generated entry/exit/internal/activity methods attached to states."""
        nodes = list(self.current.graph.nodes)
        for node in nodes:
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.generate_method_comment('Do the action when entering the state ' + state.name + '.')
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_entering_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][ENTERING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.entering, 2)
                self.indent(1), self.fd.write('}\n\n')
            if state.leaving != '':
                self.generate_method_comment('Do the action when leaving the state ' + state.name + '.')
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_leaving_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][LEAVING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.leaving, 2)
                self.indent(1), self.fd.write('}\n\n')
            if state.internal != '':
                # Initial node is already generated in the ::enter() method (this save generating one method)
                if node == '[*]':
                     continue
                self.generate_method_comment('Do the internal transition when leaving the state ' + state.name + '.')
                self.indent(1), self.fd.write('void ' + self.state_internal_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][INTERNAL TRANSITION FROM STATE ' + node + ']\\n");\n')
                self.fd.write(state.internal)
                self.indent(1), self.fd.write('}\n\n')
            if state.activity != '':
                self.generate_method_comment('Do the activity in the state ' + state.name + '.')
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_activity_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][ACTIVITY STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.activity, 2)
                self.indent(1), self.fd.write('}\n\n')

    ###########################################################################
    ### Entry point to generate the whole state machine class and all its methods.
    ###########################################################################
    def generate_state_machine_class(self):
        """Emit complete single-header C++11 state machine class definition."""
        self.generate_class_comment()
        self.fd.write('class ' + self.current.class_name + ' : public ' + self.runtime_base_class_qualified_name() + '<')
        self.fd.write(self.runtime_base_template_arguments() + '>\n')
        self.fd.write('{\n')
        self.fd.write('public: // Constructor and destructor\n\n')
        self.generate_constructor_method()
        self.generate_destructor_method()
        self.generate_enter_method()
        self.generate_exit_method()
        self.fd.write('public: // External events\n\n')
        self.generate_event_methods()
        self.fd.write('private: // Guards and actions on transitions\n\n')
        self.generate_transition_methods()
        self.fd.write('private: // Actions on states\n\n')
        self.generate_state_methods()
        self.fd.write('private: // Nested state machines\n\n')
        for sm in self.current.children:
            self.indent(1), self.fd.write(sm.class_name + ' ')
            self.fd.write(self.child_machine_instance(sm) + ';\n')
        self.fd.write('private: // Data events\n\n')
        for event, arcs in self.current.lookup_events.items():
            for arg in event.params:
                self.indent(1), self.fd.write('/** @brief Data for event ' + event.name + ' */\n')
                self.indent(1), self.fd.write(arg.upper() + ' ' + arg + ';\n')
        self.fd.write('\nprivate: // Client code\n\n')
        self.emit_client_code_section()
        self.fd.write('};\n\n')

    def generate_stringify_declaration(self):
        """Emit stringify() forward declaration for split generation mode."""
        self.generate_function_comment('Convert enum states to human readable string.')
        self.fd.write('const char* stringify(' + self.current.enum_name + ' const state);\n\n')

    def generate_stringify_definition(self):
        """Emit stringify() definition for split generation mode."""
        self.generate_function_comment('Convert enum states to human readable string.')
        self.fd.write('const char* stringify(' + self.current.enum_name + ' const state)\n{\n')
        self.indent(1), self.fd.write('static const char* s_states[] =\n')
        self.indent(1), self.fd.write('{\n')
        for state in list(self.current.graph.nodes):
            self.indent(2), self.fd.write('[int(' + self.state_enum(state) + ')] = "' + state + '",\n')
        self.indent(1), self.fd.write('};\n\n')
        self.indent(1), self.fd.write('return s_states[int(state)];\n')
        self.fd.write('}\n\n')

    def generate_state_machine_class_declaration(self):
        """Emit class declaration used by split C++11 generation mode."""
        self.generate_class_comment()
        self.fd.write('class ' + self.current.class_name + ' : public ' + self.runtime_base_class_qualified_name() + '<')
        self.fd.write(self.runtime_base_template_arguments() + '>\n')
        self.fd.write('{\n')
        self.fd.write('public: // Constructor and destructor\n\n')
        self.indent(1), self.fd.write(self.current.class_name + '(' + self.current.extra_code.argvs + ');\n')
        self.fd.write('#if defined(MOCKABLE)\n')
        self.indent(1), self.fd.write('virtual ~' + self.current.class_name + '();\n')
        self.fd.write('#endif\n\n')
        self.indent(1), self.fd.write('void enter();\n')
        self.indent(1), self.fd.write('void exit();\n\n')

        self.fd.write('public: // External events\n\n')
        for (sm, e) in self.current.broadcasts:
            self.indent(1), self.fd.write(e.header() + ';\n')
        for event, arcs in self.current.lookup_events.items():
            if event.name != '':
                self.indent(1), self.fd.write(event.header() + ';\n')
        self.fd.write('\n')

        self.fd.write('private: // Guards and actions on transitions\n\n')
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.indent(1), self.fd.write('MOCKABLE bool ' + self.guard_function(origin, destination) + '();\n')
            if tr.action != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.transition_function(origin, destination) + '();\n')
        self.fd.write('\n')

        self.fd.write('private: // Actions on states\n\n')
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_entering_function(node, False) + '();\n')
            if state.leaving != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_leaving_function(node, False) + '();\n')
            if state.internal != '' and node != '[*]':
                self.indent(1), self.fd.write('void ' + self.state_internal_function(node, False) + '();\n')
            if state.activity != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_activity_function(node, False) + '();\n')
        self.fd.write('\n')

        self.fd.write('private: // Nested state machines\n\n')
        for sm in self.current.children:
            self.indent(1), self.fd.write(sm.class_name + ' ' + self.child_machine_instance(sm) + ';\n')

        self.fd.write('private: // Data events\n\n')
        for event, arcs in self.current.lookup_events.items():
            for arg in event.params:
                self.indent(1), self.fd.write('//! \brief Data for event ' + event.name + '\n')
                self.indent(1), self.fd.write(arg.upper() + ' ' + arg + '{};\n')

        self.fd.write('\nprivate: // Client code\n\n')
        self.emit_client_code_section()
        self.fd.write('};\n\n')

    def generate_state_machine_definitions(self):
        """Emit out-of-class method definitions for split C++11 generation mode."""
        self.generate_method_comment('Default constructor. Start from initial state and call it actions.')
        self.fd.write(self.current.class_name + '::' + self.current.class_name + '(' + self.current.extra_code.argvs + ')\n')
        self.indent(1), self.fd.write(': ' + self.runtime_base_class_name() + '(' + self.state_enum(self.current.initial_state) + ')')
        self.fd.write(self.current.extra_code.cons), self.fd.write('\n')
        self.fd.write('{\n')
        self.indent(1), self.fd.write('// Init actions on states\n')
        self.generate_table_of_states(base_depth=1)
        self.fd.write('\n')
        self.indent(1), self.fd.write('// Init user code\n')
        self.fd.write(self.current.extra_code.init)
        self.fd.write('}\n\n')

        self.fd.write('#if defined(MOCKABLE)\n')
        self.generate_method_comment('Needed because of virtual methods.')
        self.fd.write(self.current.class_name + '::~' + self.current.class_name + '() = default;\n')
        self.fd.write('#endif\n\n')

        self.generate_method_comment('Reset the state machine and nested machines. Do the initial internal transition.')
        self.fd.write('void ' + self.current.class_name + '::enter()\n{\n')
        self.indent(1), self.fd.write(self.runtime_base_class_name() + '::enter();\n')
        for sm in self.current.children:
            self.indent(1), self.fd.write(self.child_machine_instance(sm) + '.enter();\n')
        if self.current.extra_code.init != '':
            self.fd.write('\n'), self.indent(1), self.fd.write('// Init user code\n')
            self.fd.write(self.current.extra_code.init)
        if self.current.graph.nodes['[*]']['data'].internal != '':
            self.fd.write('\n'), self.indent(1), self.fd.write('// Internal transition\n')
            self.fd.write(self.current.graph.nodes['[*]']['data'].internal)
        self.fd.write('}\n\n')

        self.generate_method_comment('Reset the state machine and nested machines. Do the initial internal transition.')
        self.fd.write('void ' + self.current.class_name + '::exit()\n{\n')
        self.indent(1), self.fd.write(self.runtime_base_class_name() + '::exit();\n')
        for sm in self.current.children:
            self.indent(1), self.fd.write(self.child_machine_instance(sm) + '.exit();\n')
        self.fd.write('}\n\n')

        for (sm, e) in self.current.broadcasts:
            self.generate_method_comment('Broadcast external event.')
            self.fd.write(e.header(name=self.current.class_name + '::' + e.name) + '\n')
            self.fd.write('{ ' + self.child_machine_instance(sm) + '.' + e.caller() + '; }\n\n')

        for event, arcs in self.current.lookup_events.items():
            if event.name == '':
                continue
            self.generate_method_comment('External event.')
            self.fd.write(event.header(name=self.current.class_name + '::' + event.name) + '\n')
            self.fd.write('{\n')
            self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][EVENT %s]')
            if len(event.params) != 0:
                self.fd.write(' with params XXX')
            self.fd.write('\\n", __func__);\n\n')
            for arg in event.params:
                self.indent(1), self.fd.write(arg + ' = ' + arg + '_;\n\n')
            self.indent(1), self.fd.write('// State transition and actions\n')
            self.indent(1), self.fd.write('static const ' + self.runtime_transitions_type() + ' s_transitions =\n')
            self.indent(1), self.fd.write('{\n')
            for origin, destination in arcs:
                tr = self.current.graph[origin][destination]['data']
                self.indent(2), self.fd.write('{\n')
                self.indent(3), self.fd.write(self.state_enum(origin) + ',\n')
                self.indent(3), self.fd.write('{\n')
                self.indent(4), self.fd.write('.destination = ' + self.state_enum(destination) + ',\n')
                if tr.guard != '':
                    self.indent(4), self.fd.write('.guard = &' + self.guard_function(origin, destination, True) + ',\n')
                if tr.action != '':
                    self.indent(4), self.fd.write('.action = &' + self.transition_function(origin, destination, True) + ',\n')
                self.indent(3), self.fd.write('},\n')
                self.indent(2), self.fd.write('},\n')
            self.indent(1), self.fd.write('};\n\n')
            self.indent(1), self.fd.write('transition(s_transitions);\n')
            self.fd.write('}\n\n')

        transitions = list(self.current.graph.edges)
        for origin, destination in transitions:
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.generate_method_comment('Guard the transition from state ' + origin  + ' to state ' + destination + '.')
                self.fd.write('MOCKABLE bool ' + self.current.class_name + '::' + self.guard_function(origin, destination) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('const bool guard = (' + tr.guard + ');\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][GUARD ' + origin + ' --> ' + destination + ': ' + tr.guard + '] result: %s\\n",\n')
                self.indent(2), self.fd.write('(guard ? "true" : "false"));\n')
                self.indent(1), self.fd.write('return guard;\n')
                self.fd.write('}\n\n')
            if tr.action != '':
                self.generate_method_comment('Do the action when transitioning from state ' + origin + ' to state ' + destination + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.transition_function(origin, destination) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][TRANSITION ' + origin + ' --> ' + destination)
                if tr.action[0:2] != '//':
                    self.fd.write(': ' + tr.action + ']\\n");\n')
                else:
                    self.fd.write(']\\n");\n')
                self.indent(1), self.fd.write(tr.action + ';\n')
                self.fd.write('}\n\n')

        nodes = list(self.current.graph.nodes)
        for node in nodes:
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.generate_method_comment('Do the action when entering the state ' + state.name + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.state_entering_function(node, False) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][ENTERING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.entering, 1)
                self.fd.write('}\n\n')
            if state.leaving != '':
                self.generate_method_comment('Do the action when leaving the state ' + state.name + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.state_leaving_function(node, False) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][LEAVING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.leaving, 1)
                self.fd.write('}\n\n')
            if state.internal != '':
                if node == '[*]':
                    continue
                self.generate_method_comment('Do the internal transition when leaving the state ' + state.name + '.')
                self.fd.write('void ' + self.current.class_name + '::' + self.state_internal_function(node, False) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][INTERNAL TRANSITION FROM STATE ' + node + ']\\n");\n')
                self.fd.write(state.internal)
                self.fd.write('}\n\n')
            if state.activity != '':
                self.generate_method_comment('Do the activity in the state ' + state.name + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.state_activity_function(node, False) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][ACTIVITY STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.activity, 1)
                self.fd.write('}\n\n')

    ###########################################################################
    ### Generate the header part of the unit test file.
    ###########################################################################
    def generate_unit_tests_header(self):
        self.generate_common_header()
        self.fd.write('#define MOCKABLE virtual\n')
        self.fd.write('#include "' + self.current.class_name + '.hpp"\n')
        self.fd.write('#include <gmock/gmock.h>\n')
        self.fd.write('#include <gtest/gtest.h>\n')
        self.fd.write('#include <cstring>\n\n')

    ###########################################################################
    ### Generate the footer part of the unit test file.
    ###########################################################################
    def generate_unit_tests_footer(self):
        pass

    ###########################################################################
    ### Generate the mocked state machine class.
    ###########################################################################
    def generate_unit_tests_mocked_class(self):
        self.generate_function_comment('Mocked state machine')
        self.fd.write('class ' + self.mock_class_name() + ' : public ' + self.test_class_name())
        self.fd.write('\n{\npublic:\n')
        transitions = list(self.current.graph.edges)
        for origin, destination in transitions:
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(bool, ')
                self.fd.write(self.guard_function(origin, destination))
                self.fd.write(', (), (override));\n')
            if tr.action != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(void, ')
                self.fd.write(self.transition_function(origin, destination))
                self.fd.write(', (), (override));\n')
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(void, ')
                self.fd.write(self.state_entering_function(node, False))
                self.fd.write(', (), (override));\n')
            if state.leaving != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(void, ')
                self.fd.write(self.state_leaving_function(node, False))
                self.fd.write(', (), (override));\n')
        for event, arcs in self.current.lookup_events.items():
            for arg in event.params:
                self.indent(1), self.fd.write('// Data for event ' + event.name + '\n')
                self.indent(1), self.fd.write(arg.upper() + ' ' + arg + '{};\n')
        self.fd.write(self.current.extra_code.unit_tests)
        if self.current.extra_code.unit_tests != '':
            self.fd.write('\n')
        self.fd.write('};\n\n')

    ###########################################################################
    ### Reset mock counters.
    ###########################################################################
    def reset_mock_counters(self):
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            tr.count_guard = 0
            tr.count_action = 0
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            state.count_entering = 0
            state.count_leaving = 0

    ###########################################################################
    ### Count the number of times the entering and leaving actions are called.
    ###########################################################################
    def count_mocked_guards(self, cycle):
        self.reset_mock_counters()
        for i in range(len(cycle) - 1):
            tr = self.current.graph[cycle[i]][cycle[i+1]]['data'];
            if tr.guard != '':
                tr.count_guard += 1
            if tr.action != '':
                tr.count_action += 1
            source = self.current.graph.nodes[cycle[i]]['data']
            destination = self.current.graph.nodes[cycle[i+1]]['data']
            if source.leaving != '' and source.name != destination.name:
                source.count_leaving += 1
            if destination.entering != '' and source.name != destination.name:
                destination.count_entering += 1

    ###########################################################################
    ### Cleaning
    ###########################################################################
    def cleaning_code(self, code):
        return code.replace('        ', ' ').replace('\n', ' ').replace('"', '\\"').strip()

    ###########################################################################
    ### Generate mock guards.
    ###########################################################################
    def generate_mocked_guards(self, cycle):
        self.count_mocked_guards(cycle)
        transitions = list(self.current.graph.edges)
        for origin, destination in transitions:
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.indent(1)
                self.fd.write('EXPECT_CALL(fsm, ')
                self.fd.write(self.guard_function(origin, destination))
                self.fd.write('())')
                if tr.count_guard == 0:
                    self.fd.write('.WillRepeatedly(::testing::Return(false));\n')
                else:
                    self.fd.write('.WillRepeatedly(::testing::Invoke([](){')
                    self.fd.write(' FSM_LOGD("' + self.cleaning_code(tr.guard) + '\\n");')
                    self.fd.write(' return true; }));\n')
            if tr.action != '':
                self.indent(1)
                self.fd.write('EXPECT_CALL(fsm, ' + self.transition_function(origin, destination, False) + '())')
                self.fd.write('.Times(' + str(tr.count_action) + ')')
                if tr.count_action >= 1:
                    self.fd.write('.WillRepeatedly(::testing::Invoke([](){')
                    self.fd.write(' FSM_LOGD("' + self.cleaning_code(tr.action) + '\\n");')
                    self.fd.write(' }))')
                self.fd.write(';\n')
        nodes = list(self.current.graph.nodes)
        for node in nodes:
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.indent(1)
                self.fd.write('EXPECT_CALL(fsm, ' + self.state_entering_function(node, False) + '())')
                self.fd.write('.Times(' + str(state.count_entering) + ')')
                if state.count_entering >= 1:
                    self.fd.write('.WillRepeatedly(::testing::Invoke([](){')
                    self.fd.write(' FSM_LOGD("' + self.cleaning_code(state.entering) + '\\n");')
                    self.fd.write(' }))')
                self.fd.write(';\n')
            if state.leaving != '':
                self.indent(1)
                self.fd.write('EXPECT_CALL(fsm, ' + self.state_leaving_function(node, False) + '())')
                self.fd.write('.Times(' + str(state.count_leaving) + ')')
                if state.count_leaving >= 1:
                    self.fd.write('.WillRepeatedly(::testing::Invoke([](){')
                    self.fd.write(' FSM_LOGD("' + self.cleaning_code(state.leaving) + '\\n");')
                    self.fd.write(' }))')
                self.fd.write(';\n')

    ###########################################################################
    ### Generate mock guards.
    ###########################################################################
    def generate_mocked_actions(self, cycle):
        for i in range(len(cycle) - 1):
            tr = self.current.graph[cycle[i]][cycle[i+1]]['data'];
            if tr.guard != '':
                tr.count_guard += 1
            if tr.action != '':
                tr.count_action += 1
        for node in cycle:
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                state.count_entering += 1
            if state.leaving != '':
                state.count_leaving += 1

    ###########################################################################
    ### Generate checks on initial state
    ###########################################################################
    def generate_unit_tests_check_initial_state(self):
        self.generate_line_separator(0, ' ', 80, '-')
        self.fd.write('TEST(' + self.test_suite_name() + ', TestInitialSate)\n{\n')
        self.indent(1), self.fd.write('FSM_LOGD("===============================================\\n");\n')
        self.indent(1), self.fd.write('FSM_LOGD("Check initial state after constructor or reset.\\n");\n')
        self.indent(1), self.fd.write('FSM_LOGD("===============================================\\n");\n')
        self.indent(1), self.fd.write(self.test_class_name() + ' fsm; // Not mocked !\n')
        self.indent(1), self.fd.write('fsm.enter();\n\n')
        self.generate_unit_tests_assertions_initial_state()
        self.fd.write('}\n\n')

    ###########################################################################
    ### Generate checks on all cycles
    ###########################################################################
    def generate_unit_tests_check_cycles(self):
        count = 0
        cycles = self.current.graph_cycles()
        for cycle in cycles:
            self.generate_line_separator(0, ' ', 80, '-')
            self.fd.write('TEST(' + self.test_suite_name() + ', TestCycle' + str(count) + ')\n{\n')
            count += 1
            # Print the cycle
            self.indent(1), self.fd.write('FSM_LOGD("===========================================\\n");\n')
            self.indent(1), self.fd.write('FSM_LOGD("Check cycle: [*]')
            for c in cycle:
                self.fd.write(' ' + c)
            self.fd.write('\\n");\n')
            self.indent(1), self.fd.write('FSM_LOGD("===========================================\\n");\n')

            # Reset the state machine and print the guard supposed to reach this state
            self.indent(1), self.fd.write(self.mock_class_name() + ' ' + 'fsm;\n')
            self.generate_mocked_guards(['[*]'] + cycle)
            self.fd.write('\n'), self.indent(1), self.fd.write('fsm.enter();\n')
            guard = self.current.graph[self.current.initial_state][cycle[0]]['data'].guard
            self.indent(1), self.fd.write('FSM_LOGD("[UNIT TEST] Current state: %s\\n", fsm.c_str());\n')
            self.indent(1), self.fd.write('ASSERT_EQ(fsm.state(), ' + self.state_enum_for_tests(cycle[0]) + ');\n')
            self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[0] + '");\n')

            # Iterate on all nodes of the cycle
            for i in range(len(cycle) - 1):
# FIXME
#                # External event not leaving the current state
#                if self.current.graph.has_edge(cycle[i], cycle[i]) and (cycle[i] != cycle[i+1]):
#                    tr = self.current.graph[cycle[i]][cycle[i]]['data']
#                    if tr.event.name != '':
#                        self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + ']// Event ' + tr.event.name + ' [' + tr.guard + ']: ' + cycle[i] + ' <--> ' + cycle[i] + '\\n");\n')
#                        self.indent(1), self.fd.write('fsm.' + tr.event.caller('fsm') + ';')
#                        if tr.guard != '':
#                            self.fd.write(' // If ' + tr.guard)
#                        self.fd.write('\n')
#                        self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '] Current state: %s\\n", fsm.c_str());\n')
#                        self.indent(1), self.fd.write('ASSERT_EQ(fsm.state(), ' + self.state_enum(cycle[i]) + ');\n')
#                        self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i] + '");\n')

                # External event: print the name of the event + its guard
                tr = self.current.graph[cycle[i]][cycle[i+1]]['data']
                if tr.event.name != '':
                    self.fd.write('\n'), self.indent(1)
                    self.fd.write('FSM_LOGD("\\n[' + self.current.class_name.upper() + '] Triggering event ' + tr.event.name + ' [' + tr.guard + ']: ' + cycle[i] + ' ==> ' + cycle[i + 1] + '\\n");\n')
                    self.indent(1), self.fd.write('fsm.' + tr.event.caller('fsm') + ';\n')

                if (i == len(cycle) - 2):
                    # Cycle of non external evants => malformed state machine
                    # I think this case is not good
                    if self.current.graph[cycle[i+1]][cycle[1]]['data'].event.name == '':
                        self.indent(1), self.fd.write('\n#warning "Malformed state machine: unreachable destination state"\n')
                    else:
                        # No explicit event => direct internal transition to the state if an explicit event can occures.
                        self.indent(1), self.fd.write('FSM_LOGD("[UNIT TEST] Current state: %s\\n", fsm.c_str());\n')
                        self.indent(1), self.fd.write('ASSERT_EQ(fsm.state(), ' + self.state_enum_for_tests(cycle[i+1]) + ');\n')
                        self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i+1] + '");\n')

                # No explicit event => direct internal transition to the state if an explicit event can occures.
                # Else skip test for the destination state since we cannot test its internal state
                elif self.current.graph[cycle[i+1]][cycle[i+2]]['data'].event.name != '':
                    self.indent(1), self.fd.write('FSM_LOGD("[UNIT TEST] Current state: %s\\n", fsm.c_str());\n')
                    self.indent(1), self.fd.write('ASSERT_EQ(fsm.state(), ' + self.state_enum_for_tests(cycle[i+1]) + ');\n')
                    self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i+1] + '");\n')
            self.fd.write('}\n\n')

    ###########################################################################
    ### Generate checks on pathes to all sinks
    ###########################################################################
    def generate_unit_tests_pathes_to_sinks(self):
        count = 0
        pathes = self.current.graph_all_paths_to_sinks()
        for path in pathes:
            self.generate_line_separator(0, ' ', 80, '-')
            self.fd.write('TEST(' + self.test_suite_name() + ', TestPath' + str(count) + ')\n{\n')
            count += 1
            # Print the path
            self.indent(1), self.fd.write('FSM_LOGD("===========================================\\n");\n')
            self.indent(1), self.fd.write('FSM_LOGD("Check path:')
            for c in path:
                self.fd.write(' ' + c)
            self.fd.write('\\n");\n')
            self.indent(1), self.fd.write('FSM_LOGD("===========================================\\n");\n')

            # Reset the state machine and print the guard supposed to reach this state
            self.indent(1), self.fd.write(self.mock_class_name() + ' ' + 'fsm;\n')
            self.generate_mocked_guards(path)
            self.fd.write('\n'), self.indent(1), self.fd.write('fsm.enter();\n')

            # Iterate on all nodes of the path
            for i in range(len(path) - 1):
                event = self.current.graph[path[i]][path[i+1]]['data'].event
                if event.name != '':
                    guard = self.current.graph[path[i]][path[i+1]]['data'].guard
                    self.fd.write('\n'), self.indent(1)
                    self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '] Event ' + event.name + ' [' + guard + ']: ' + path[i] + ' ==> ' + path[i + 1] + '\\n");\n')
                    self.fd.write('\n'), self.indent(1), self.fd.write('fsm.' + event.caller() + ';\n')
                if (i == len(path) - 2):
                    self.indent(1), self.fd.write('FSM_LOGD("[UNIT TEST] Current state: %s\\n", fsm.c_str());\n')
                    self.indent(1), self.fd.write('ASSERT_EQ(fsm.state(), ' + self.state_enum_for_tests(path[i+1]) + ');\n')
                    self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + path[i+1] + '");\n')
                elif self.current.graph[path[i+1]][path[i+2]]['data'].event.name != '':
                    self.indent(1), self.fd.write('FSM_LOGD("[UNIT TEST] Current state: %s\\n", fsm.c_str());\n')
                    self.indent(1), self.fd.write('ASSERT_EQ(fsm.state(), ' + self.state_enum_for_tests(path[i+1]) + ');\n')
                    self.indent(1), self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + path[i+1] + '");\n')
            self.fd.write('}\n\n')

    ###########################################################################
    ### Generate the main function doing unit tests
    ###########################################################################
    def generate_unit_tests_main_function(self, filename, files):
        self.generate_function_comment(
            'Compile with one of the following line:\n'
            '//! g++ --std=c++14 -Wall -Wextra -Wshadow '
            '-I../../include -DFSM_DEBUG \n//! '
            + ' '.join(files) + ' \n//! ' + filename +
            ' `pkg-config --cflags --libs gtest gmock`')
        self.fd.write('int main(int argc, char *argv[])\n{\n')
        self.indent(1), self.fd.write('// The following line must be executed to initialize Google Mock\n')
        self.indent(1), self.fd.write('// (and Google Test) before running the tests.\n')
        self.indent(1), self.fd.write('::testing::InitGoogleMock(&argc, argv);\n')
        self.indent(1), self.fd.write('return RUN_ALL_TESTS();\n')
        self.fd.write('}\n')

    ###########################################################################
    ### Generate the main function doing unit tests
    ###########################################################################
    def generate_unit_tests_main_file(self, filename, files):
        def emit():
            self.fd.write('#include <gmock/gmock.h>\n')
            self.fd.write('#include <gtest/gtest.h>\n')
            self.generate_unit_tests_main_function(filename, files)

        emit_to_file(self, filename, emit)

    ###########################################################################
    ### Code generator: Add an example of how using this state machine. It
    ### gets all cycles in the graph and try them. This example can be used as
    ### partial unit test. Not all cases can be generated since I dunno how to
    ### parse guards to generate range of inputs.
    ### FIXME Manage guard logic to know where to pass in edges.
    ### FIXME Cycles does not make all test case possible
    ###########################################################################
    def generate_unit_tests(self, cxxfile, files, separated):
        filename = self.current.class_name + self.tests_file_suffix()

        def emit():
            self.generate_unit_tests_header()
            self.generate_unit_tests_mocked_class()
            self.generate_unit_tests_check_cycles()
            self.generate_unit_tests_pathes_to_sinks()
            if not separated:
                self.generate_unit_tests_main_function(filename, files)
            self.generate_unit_tests_footer()

        emit_to_file(self, os.path.join(os.path.dirname(cxxfile), filename), emit)

    ###########################################################################
    ### Code generator: generate the code of the state machine
    ###########################################################################
    def generate_state_machine(self, cxxfile):
        hpp = self.is_hpp_file(cxxfile)

        def emit():
            self.generate_header(hpp)
            self.generate_namespace_begin()
            self.generate_state_enums()
            self.generate_stringify_function()
            self.generate_state_machine_class()
            self.generate_namespace_end()
            self.generate_footer(hpp)

        emit_to_file(self, cxxfile, emit)

    def generate_state_machine_split(self, hpp_target, cpp_target):
        def emit_hpp():
            self.generate_header(True)
            self.generate_namespace_begin()
            self.generate_state_enums()
            self.generate_stringify_declaration()
            self.generate_state_machine_class_declaration()
            self.generate_namespace_end()
            self.generate_footer(True)

        emit_to_file(self, hpp_target, emit_hpp)

        def emit_cpp():
            self.generate_common_header()
            self.generate_include(0, '"', self.current.class_name + '.hpp', '"')
            self.fd.write('\n')
            self.generate_include(0, '<', 'array', '>')
            self.generate_include(0, '<', 'cassert', '>')
            self.generate_include(0, '<', 'cstdlib', '>')
            self.generate_include(0, '<', 'map', '>')
            self.generate_include(0, '<', 'mutex', '>')
            self.generate_include(0, '<', 'queue', '>')
            self.generate_include(0, '<', 'cstdio', '>')
            self.fd.write('\n')
            self.generate_namespace_begin()
            self.method_comment_indent = 0
            self.generate_stringify_definition()
            self.generate_state_machine_definitions()
            self.method_comment_indent = 4
            self.generate_namespace_end()

        emit_to_file(self, cpp_target, emit_cpp)

    ###########################################################################
    ### Code generator: entry point generating C++ files: state machine, tests,
    ### macros ...
    ### param[in] separated if False then the main() function is generated in
    ### the same file else in a separated.
    ###########################################################################
    def generate_cxx_code(self, cxxfile, separated):
        generate_cpp11_backend(self, cxxfile, separated)

    ###########################################################################
    ### C++20 std::variant / std::visit backend.
    ### The generated class is self-contained (no base class). The current state
    ### is held as a std::variant of lightweight tag structs. Each external event
    ### dispatches via std::visit(fsm::overloaded{...}, m_state).
    ###########################################################################

    def generate_variant_header(self, hpp):
        """Like generate_header but includes state_machine_variant.hpp."""
        indent = 1 if hpp else 0
        self.generate_common_header()
        if hpp:
            self.fd.write('#pragma once\n')
            self.fd.write('#ifndef ' + self.current.class_name.upper() + '_HPP\n')
            self.fd.write('#define ' + self.current.class_name.upper() + '_HPP\n\n')
        for sm in self.current.children:
            self.generate_include(indent, '"', sm.class_name + '.hpp', '"')
        if len(self.current.children) == 0:
            self.generate_include(indent, '"', 'state_machine_variant.hpp', '"')
            self.fd.write('\n')
            self.generate_include(indent, '<', 'cstdio', '>')
            self.generate_include(indent, '<', 'cstring', '>')
            self.generate_include(indent, '<', 'mutex', '>')
            self.generate_include(indent, '<', 'optional', '>')
            self.generate_include(indent, '<', 'type_traits', '>')
            self.generate_include(indent, '<', 'utility', '>')
            self.generate_include(indent, '<', 'variant', '>')
            self.fd.write('\n')
        for w in self.current.warnings:
            self.fd.write('\n#warning "' + w + '"\n')
        if hpp:
            self.fd.write('// Provide a default empty MOCKABLE for non-testing builds.\n')
            self.fd.write('#ifndef MOCKABLE\n')
            self.fd.write('#define MOCKABLE\n')
            self.fd.write('#endif\n')
        self.fd.write(self.current.extra_code.header)
        self.fd.write('\n')

    def generate_variant_state_structs(self):
        """Generate one empty tag struct per state for std::variant."""
        self.generate_function_comment('State tags for std::variant.')
        for state in list(self.current.graph.nodes):
            if state == '[*]':
                continue
            name = self.state_name(state)
            comment = self.current.graph.nodes[state]['data'].comment
            if comment != '':
                self.fd.write('/**< ' + comment + ' */\n')
            self.fd.write('struct ' + name + ' {}; \n')
        self.fd.write('\n')

    def generate_variant_state_alias(self):
        """Generate: using State = std::variant<A, B, ...>;"""
        states = [self.state_name(s) for s in list(self.current.graph.nodes)
                  if s != '[*]']
        self.indent(1)
        self.fd.write('using ' + self.variant_state_alias() + ' = std::variant<')
        self.fd.write(', '.join(states))
        self.fd.write('>;\n\n')

    def emit_variant_thread_safety_lock(self, depth):
        if self.thread_safe:
            self.indent(depth), self.fd.write('std::lock_guard<std::mutex> lock(m_mutex);\n')
            self.fd.write('\n')

    def emit_variant_thread_safety_member(self, depth):
        if self.thread_safe:
            self.indent(depth), self.fd.write('mutable std::mutex m_mutex;\n')

    def generate_variant_c_str(self):
        """Generate c_str() that visits the variant and returns a string literal."""
        self.generate_method_comment('Return the current state as a C string.')
        self.indent(1), self.fd.write('const char* c_str() const\n')
        self.indent(1), self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(2)
        self.indent(2), self.fd.write('return std::visit(fsm::overloaded{\n')
        for state in list(self.current.graph.nodes):
            if state == '[*]':
                continue
            name = self.state_name(state)
            label = 'DESTRUCTOR' if state == '*' else state
            self.indent(3)
            self.fd.write('[](')
            self.fd.write(name + ' const&) { return "' + label + '"; },\n')
        self.indent(2), self.fd.write('}, m_state);\n')
        self.indent(1), self.fd.write('}\n\n')

    def generate_variant_is_method(self):
        """Generate template<typename S> bool is() const."""
        self.generate_method_comment('Return true if the FSM is currently in state S.')
        self.indent(1), self.fd.write('template<typename S>\n')
        self.indent(1), self.fd.write('bool is() const\n')
        self.indent(1), self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(2)
        self.indent(2), self.fd.write('return std::holds_alternative<S>(m_state);\n')
        self.indent(1), self.fd.write('}\n\n')

    def _emit_variant_noevents(self, state, depth):
        """Inline any eventless (no-event) outgoing transitions from a state."""
        for dest in list(self.current.graph.neighbors(state)):
            tr = self.current.graph[state][dest]['data']
            if tr.event.name != '':
                continue
            dest_name = self.state_name(dest)
            if tr.guard != '':
                self.indent(depth)
                self.fd.write('if (' + self.guard_function(state, dest) + '())\n')
                self.indent(depth), self.fd.write('{\n')
                inner = depth + 1
            else:
                inner = depth
            src_data = self.current.graph.nodes[state]['data']
            if src_data.leaving != '':
                self.indent(inner)
                self.fd.write(self.state_leaving_function(state) + '();\n')
            if tr.action != '':
                self.indent(inner)
                self.fd.write(self.transition_function(state, dest) + '();\n')
            self.indent(inner), self.fd.write('m_state = ' + dest_name + '{};\n')
            dest_data = self.current.graph.nodes[dest]['data']
            if dest_data.entering != '':
                self.indent(inner)
                self.fd.write(self.state_entering_function(dest) + '();\n')
            if tr.guard != '':
                self.indent(inner), self.fd.write('return;\n')
                self.indent(depth), self.fd.write('}\n')

    def generate_variant_enter_method(self):
        """Generate enter(): reset FSM to initial state via guarded [*] transitions."""
        self.generate_method_comment('Reset the FSM to its initial state.')
        self.indent(1), self.fd.write('void enter()\n')
        self.indent(1), self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(2)
        self.indent(2), self.fd.write('m_enabled = true;\n')
        if self.current.extra_code.init != '':
            self.fd.write(self.current.extra_code.init)
        neighbors = [n for n in list(self.current.graph.neighbors('[*]'))
                     if n not in ['[*]', '*']]
        if len(neighbors) == 1:
            dest = neighbors[0]
            dest_name = self.state_name(dest)
            tr = self.current.graph['[*]'][dest]['data']
            if tr.guard != '':
                self.fd.write('\n')
                self.indent(2)
                self.fd.write('if (' + self.guard_function('[*]', dest) + '())\n')
                self.indent(2), self.fd.write('{\n')
                self.indent(3), self.fd.write('m_state = ' + dest_name + '{};\n')
                dest_data = self.current.graph.nodes[dest]['data']
                if dest_data.entering != '':
                    self.indent(3)
                    self.fd.write(self.state_entering_function(dest) + '();\n')
                self._emit_variant_noevents(dest, 3)
                self.indent(2), self.fd.write('}\n')
            else:
                self.indent(2), self.fd.write('m_state = ' + dest_name + '{};\n')
                dest_data = self.current.graph.nodes[dest]['data']
                if dest_data.entering != '':
                    self.indent(2)
                    self.fd.write(self.state_entering_function(dest) + '();\n')
                self._emit_variant_noevents(dest, 2)
        else:
            for index, dest in enumerate(neighbors):
                if index != 0:
                    self.fd.write('\n')
                tr = self.current.graph['[*]'][dest]['data']
                dest_name = self.state_name(dest)
                if tr.guard != '':
                    self.indent(2)
                    self.fd.write('if (' + self.guard_function('[*]', dest) + '())\n')
                    self.indent(2), self.fd.write('{\n')
                    self.indent(3), self.fd.write('m_state = ' + dest_name + '{};\n')
                    dest_data = self.current.graph.nodes[dest]['data']
                    if dest_data.entering != '':
                        self.indent(3)
                        self.fd.write(self.state_entering_function(dest) + '();\n')
                    self._emit_variant_noevents(dest, 3)
                    self.indent(3), self.fd.write('return;\n')
                    self.indent(2), self.fd.write('}\n')
                else:
                    self.indent(2), self.fd.write('m_state = ' + dest_name + '{};\n')
                    dest_data = self.current.graph.nodes[dest]['data']
                    if dest_data.entering != '':
                        self.indent(2)
                        self.fd.write(self.state_entering_function(dest) + '();\n')
                    self._emit_variant_noevents(dest, 2)
        self.indent(1), self.fd.write('}\n\n')

    def _group_variant_event_arcs(self, arcs):
        grouped = dict()
        for origin, destination in arcs:
            if origin in ['[*]', '*']:
                continue
            if origin not in grouped:
                grouped[origin] = []
            grouped[origin].append(destination)
        return grouped.items()

    def _emit_variant_event_transition_body(self, origin, destination, indent_level):
        tr = self.current.graph[origin][destination]['data']
        if origin == destination:
            if tr.action != '':
                self.indent(indent_level)
                self.fd.write(self.transition_function(origin, destination) + '();\n')
            return

        origin_data = self.current.graph.nodes[origin]['data']
        if origin_data.leaving != '':
            self.indent(indent_level)
            self.fd.write(self.state_leaving_function(origin) + '();\n')
        if tr.action != '':
            self.indent(indent_level)
            self.fd.write(self.transition_function(origin, destination) + '();\n')
        self.indent(indent_level), self.fd.write('m_state = ' + self.state_name(destination) + '{};\n')
        dest_data = self.current.graph.nodes[destination]['data']
        if dest_data.entering != '':
            self.indent(indent_level)
            self.fd.write(self.state_entering_function(destination) + '();\n')
        self._emit_variant_noevents(destination, indent_level)

    def _emit_variant_event_dispatch_cases(self, arcs, indent_level):
        for origin, destinations in self._group_variant_event_arcs(arcs):
            self.indent(indent_level), self.fd.write('[this](' + self.state_name(origin) + '&)\n')
            self.indent(indent_level), self.fd.write('{\n')
            for destination in destinations:
                tr = self.current.graph[origin][destination]['data']
                if tr.guard != '':
                    self.indent(indent_level + 1), self.fd.write('if (' + self.guard_function(origin, destination) + '())\n')
                    self.indent(indent_level + 1), self.fd.write('{\n')
                    self._emit_variant_event_transition_body(origin, destination, indent_level + 2)
                    self.indent(indent_level + 2), self.fd.write('return;\n')
                    self.indent(indent_level + 1), self.fd.write('}\n')
                else:
                    self._emit_variant_event_transition_body(origin, destination, indent_level + 1)
                    self.indent(indent_level + 1), self.fd.write('return;\n')
                    break
            self.indent(indent_level), self.fd.write('},\n')

    def generate_variant_event_methods(self):
        """Generate external event methods using std::visit / fsm::overloaded."""
        for (sm, e) in self.current.broadcasts:
            self.generate_method_comment('Broadcast external event.')
            self.indent(1), self.fd.write('inline '), self.fd.write(e.header() + '\n')
            self.indent(1), self.fd.write('{\n')
            self.emit_variant_thread_safety_lock(2)
            self.indent(2), self.fd.write(self.child_machine_instance(sm) + '.' + e.caller() + ';\n')
            self.indent(1), self.fd.write('}\n\n')
        for event, arcs in self.current.lookup_events.items():
            if event.name == '':
                continue
            self.generate_method_comment('External event.')
            self.indent(1), self.fd.write(event.header() + '\n')
            self.indent(1), self.fd.write('{\n')
            self.emit_variant_thread_safety_lock(2)
            for arg in event.params:
                self.indent(2), self.fd.write(arg + ' = ' + arg + '_;\n')
            if event.params:
                self.fd.write('\n')
            self.indent(2)
            self.fd.write('FSM_LOGD("[' + self.current.class_name.upper()
                          + '][EVENT %s]\\n", __func__);\n\n')
            self.indent(2), self.fd.write('std::visit(fsm::overloaded{\n')
            self._emit_variant_event_dispatch_cases(arcs, 3)
            self.indent(3), self.fd.write('[](auto&) { /* ignore */ }\n')
            self.indent(2), self.fd.write('}, m_state);\n')
            self.indent(1), self.fd.write('}\n\n')

    def generate_variant_state_methods(self):
        """Emit onEntering_*/onLeaving_* methods (skips internal-transition methods used in C++11 backend)."""
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.generate_method_comment('Action on entering state ' + state.name + '.')
                self.indent(1)
                self.fd.write('MOCKABLE void ' + self.state_entering_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2)
                self.fd.write('FSM_LOGD("[' + self.current.class_name.upper()
                              + '][ENTERING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.entering, 2)
                self.indent(1), self.fd.write('}\n\n')
            if state.leaving != '':
                self.generate_method_comment('Action on leaving state ' + state.name + '.')
                self.indent(1)
                self.fd.write('MOCKABLE void ' + self.state_leaving_function(node, False) + '()\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2)
                self.fd.write('FSM_LOGD("[' + self.current.class_name.upper()
                              + '][LEAVING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.leaving, 2)
                self.indent(1), self.fd.write('}\n\n')

    def generate_variant_state_machine_class(self):
        """Generate the complete self-contained C++20 std::variant FSM class."""
        self.generate_class_comment()
        self.fd.write('class ' + self.current.class_name + '\n{\npublic:\n\n')
        self.generate_variant_state_alias()
        self.generate_method_comment('Constructor. Calls enter() to set the initial state.')
        self.indent(1)
        self.fd.write(self.current.class_name + '(' + self.current.extra_code.argvs + ')\n')
        if self.current.extra_code.cons != '':
            # [cons] entries are stored with a leading ", " (designed for C++11's
            # ": StateMachine(...), member(val)" pattern). Strip leading comma here.
            cons = self.current.extra_code.cons.strip().lstrip(',').strip()
            self.indent(2), self.fd.write(': ' + cons + '\n')
        self.indent(1), self.fd.write('{\n')
        self.indent(2), self.fd.write('enter();\n')
        self.indent(1), self.fd.write('}\n\n')
        self.fd.write('#if defined(MOCKABLE)\n')
        self.generate_method_comment('Virtual destructor (needed when MOCKABLE=virtual).')
        self.indent(1)
        self.fd.write('virtual ~' + self.current.class_name + '() = default;\n')
        self.fd.write('#endif\n\n')
        self.generate_variant_enter_method()
        self.indent(1), self.fd.write('void exit()\n')
        self.indent(1), self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(2)
        self.indent(2), self.fd.write('m_enabled = false;\n')
        self.indent(1), self.fd.write('}\n')
        self.indent(1), self.fd.write('bool ' + self.active_method_name() + '() const\n')
        self.indent(1), self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(2)
        self.indent(2), self.fd.write('return m_enabled;\n')
        self.indent(1), self.fd.write('}\n\n')
        self.generate_variant_c_str()
        self.generate_variant_is_method()
        self.fd.write('public: // External events\n\n')
        self.generate_variant_event_methods()
        self.fd.write('private: // Guards and actions on transitions\n\n')
        self.generate_transition_methods()
        self.fd.write('private: // Actions on states\n\n')
        self.generate_variant_state_methods()
        self.fd.write('private: // Nested state machines\n\n')
        for sm in self.current.children:
            self.indent(1), self.fd.write(sm.class_name + ' ')
            self.fd.write(self.child_machine_instance(sm) + ';\n')
        self.fd.write('private: // Data event members\n\n')
        for event, arcs in self.current.lookup_events.items():
            for arg in event.params:
                self.indent(1)
                self.fd.write('/**< Data for event ' + event.name + ' */\n')
                self.indent(1), self.fd.write(arg.upper() + ' ' + arg + ';\n')
        self.fd.write('\nprivate: // Client code\n\n')
        self.emit_client_code_section()
        self.fd.write('\nprivate:\n')
        self.indent(1), self.fd.write(self.variant_state_alias() + ' m_state;\n')
        self.indent(1), self.fd.write('bool  m_enabled = false;\n')
        self.emit_variant_thread_safety_member(1)
        self.fd.write('};\n\n')

    def generate_variant_state_machine(self, cxxfile):
        """Write the complete C++20-variant FSM to a header/source file."""
        hpp = self.is_hpp_file(cxxfile)

        def emit():
            self.generate_variant_header(hpp)
            self.generate_namespace_begin()
            self.generate_variant_state_structs()
            self.generate_variant_state_machine_class()
            self.generate_namespace_end()
            self.generate_footer(hpp)

        emit_to_file(self, cxxfile, emit)

    def generate_variant_state_machine_class_declaration(self):
        self.generate_class_comment()
        self.fd.write('class ' + self.current.class_name + '\n{\npublic:\n\n')
        self.generate_variant_state_alias()
        self.indent(1), self.fd.write(self.current.class_name + '(' + self.current.extra_code.argvs + ');\n')
        self.fd.write('#if defined(MOCKABLE)\n')
        self.indent(1), self.fd.write('virtual ~' + self.current.class_name + '();\n')
        self.fd.write('#endif\n')
        self.indent(1), self.fd.write('void enter();\n')
        self.indent(1), self.fd.write('void exit();\n')
        self.indent(1), self.fd.write('bool ' + self.active_method_name() + '() const;\n')
        self.indent(1), self.fd.write('const char* c_str() const;\n\n')

        self.generate_variant_is_method()

        self.fd.write('public: // External events\n\n')
        for (sm, e) in self.current.broadcasts:
            self.indent(1), self.fd.write(e.header() + ';\n')
        for event, arcs in self.current.lookup_events.items():
            if event.name != '':
                self.indent(1), self.fd.write(event.header() + ';\n')

        self.fd.write('\nprivate: // Guards and actions on transitions\n\n')
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.indent(1), self.fd.write('MOCKABLE bool ' + self.guard_function(origin, destination) + '();\n')
            if tr.action != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.transition_function(origin, destination) + '();\n')

        self.fd.write('\nprivate: // Actions on states\n\n')
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_entering_function(node, False) + '();\n')
            if state.leaving != '':
                self.indent(1), self.fd.write('MOCKABLE void ' + self.state_leaving_function(node, False) + '();\n')

        self.fd.write('\nprivate: // Nested state machines\n\n')
        for sm in self.current.children:
            self.indent(1), self.fd.write(sm.class_name + ' ' + self.child_machine_instance(sm) + ';\n')

        self.fd.write('\nprivate: // Data event members\n\n')
        for event, arcs in self.current.lookup_events.items():
            for arg in event.params:
                self.indent(1), self.fd.write('/**< Data for event ' + event.name + ' */\n')
                self.indent(1), self.fd.write(arg.upper() + ' ' + arg + ';\n')

        self.fd.write('\nprivate: // Client code\n\n')
        self.emit_client_code_section()
        self.fd.write('\nprivate:\n')
        self.indent(1), self.fd.write(self.variant_state_alias() + ' m_state;\n')
        self.indent(1), self.fd.write('bool  m_enabled = false;\n')
        self.emit_variant_thread_safety_member(1)
        self.fd.write('};\n\n')

    def generate_variant_c_str_definition(self):
        self.generate_method_comment('Return the current state as a C string.')
        self.fd.write('const char* ' + self.current.class_name + '::c_str() const\n')
        self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(1)
        self.indent(1), self.fd.write('return std::visit(fsm::overloaded{\n')
        for state in list(self.current.graph.nodes):
            if state == '[*]':
                continue
            name = self.state_name(state)
            label = 'DESTRUCTOR' if state == '*' else state
            self.indent(2), self.fd.write('[](' + name + ' const&) { return "' + label + '"; },\n')
        self.indent(2), self.fd.write('[](auto const&) { return "DESTRUCTOR"; },\n')
        self.indent(1), self.fd.write('}, m_state);\n')
        self.fd.write('}\n\n')

    def generate_variant_enter_method_definition(self):
        self.generate_method_comment('Reset the FSM to its initial state.')
        self.fd.write('void ' + self.current.class_name + '::enter()\n')
        self.fd.write('{\n')
        self.emit_variant_thread_safety_lock(1)
        self.indent(1), self.fd.write('m_enabled = true;\n')
        if self.current.extra_code.init != '':
            self.fd.write(self.current.extra_code.init)
        neighbors = [n for n in list(self.current.graph.neighbors('[*]')) if n not in ['[*]', '*']]
        if len(neighbors) == 1:
            dest = neighbors[0]
            dest_name = self.state_name(dest)
            tr = self.current.graph['[*]'][dest]['data']
            if tr.guard != '':
                self.fd.write('\n')
                self.indent(1), self.fd.write('if (' + self.guard_function('[*]', dest) + '())\n')
                self.indent(1), self.fd.write('{\n')
                self.indent(2), self.fd.write('m_state = ' + dest_name + '{};\n')
                dest_data = self.current.graph.nodes[dest]['data']
                if dest_data.entering != '':
                    self.indent(2), self.fd.write(self.state_entering_function(dest) + '();\n')
                self._emit_variant_noevents(dest, 2)
                self.indent(1), self.fd.write('}\n')
            else:
                self.indent(1), self.fd.write('m_state = ' + dest_name + '{};\n')
                dest_data = self.current.graph.nodes[dest]['data']
                if dest_data.entering != '':
                    self.indent(1), self.fd.write(self.state_entering_function(dest) + '();\n')
                self._emit_variant_noevents(dest, 1)
        else:
            for index, dest in enumerate(neighbors):
                if index != 0:
                    self.fd.write('\n')
                tr = self.current.graph['[*]'][dest]['data']
                dest_name = self.state_name(dest)
                if tr.guard != '':
                    self.indent(1), self.fd.write('if (' + self.guard_function('[*]', dest) + '())\n')
                    self.indent(1), self.fd.write('{\n')
                    self.indent(2), self.fd.write('m_state = ' + dest_name + '{};\n')
                    dest_data = self.current.graph.nodes[dest]['data']
                    if dest_data.entering != '':
                        self.indent(2), self.fd.write(self.state_entering_function(dest) + '();\n')
                    self._emit_variant_noevents(dest, 2)
                    self.indent(2), self.fd.write('return;\n')
                    self.indent(1), self.fd.write('}\n')
                else:
                    self.indent(1), self.fd.write('m_state = ' + dest_name + '{};\n')
                    dest_data = self.current.graph.nodes[dest]['data']
                    if dest_data.entering != '':
                        self.indent(1), self.fd.write(self.state_entering_function(dest) + '();\n')
                    self._emit_variant_noevents(dest, 1)
        self.fd.write('}\n\n')

    def generate_variant_event_method_definitions(self):
        for (sm, e) in self.current.broadcasts:
            self.generate_method_comment('Broadcast external event.')
            self.fd.write(e.header(name=self.current.class_name + '::' + e.name) + '\n')
            self.fd.write('{\n')
            self.emit_variant_thread_safety_lock(1)
            self.indent(1), self.fd.write(self.child_machine_instance(sm) + '.' + e.caller() + ';\n')
            self.fd.write('}\n\n')

        for event, arcs in self.current.lookup_events.items():
            if event.name == '':
                continue
            self.generate_method_comment('External event.')
            self.fd.write(event.header(name=self.current.class_name + '::' + event.name) + '\n')
            self.fd.write('{\n')
            self.emit_variant_thread_safety_lock(1)
            for arg in event.params:
                self.indent(1), self.fd.write(arg + ' = ' + arg + '_;\n')
            if event.params:
                self.fd.write('\n')
            self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][EVENT %s]\\n", __func__);\n\n')
            self.indent(1), self.fd.write('std::visit(fsm::overloaded{\n')
            self._emit_variant_event_dispatch_cases(arcs, 2)
            self.indent(2), self.fd.write('[](auto&) { /* ignore */ }\n')
            self.indent(1), self.fd.write('}, m_state);\n')
            self.fd.write('}\n\n')

    def generate_variant_transition_method_definitions(self):
        transitions = list(self.current.graph.edges)
        for origin, destination in transitions:
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.generate_method_comment('Guard the transition from state ' + origin + ' to state ' + destination + '.')
                self.fd.write('MOCKABLE bool ' + self.current.class_name + '::' + self.guard_function(origin, destination) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('const bool guard = (' + tr.guard + ');\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][GUARD ' + origin + ' --> ' + destination + ': ' + tr.guard + '] result: %s\\n",\n')
                self.indent(2), self.fd.write('(guard ? "true" : "false"));\n')
                self.indent(1), self.fd.write('return guard;\n')
                self.fd.write('}\n\n')
            if tr.action != '':
                self.generate_method_comment('Do the action when transitioning from state ' + origin + ' to state ' + destination + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.transition_function(origin, destination) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][TRANSITION ' + origin + ' --> ' + destination)
                if tr.action[0:2] != '//':
                    self.fd.write(': ' + tr.action + ']\\n");\n')
                else:
                    self.fd.write(']\\n");\n')
                self.indent(1), self.fd.write(tr.action + ';\n')
                self.fd.write('}\n\n')

    def generate_variant_state_method_definitions(self):
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.generate_method_comment('Action on entering state ' + state.name + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.state_entering_function(node, False) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][ENTERING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.entering, 1)
                self.fd.write('}\n\n')
            if state.leaving != '':
                self.generate_method_comment('Action on leaving state ' + state.name + '.')
                self.fd.write('MOCKABLE void ' + self.current.class_name + '::' + self.state_leaving_function(node, False) + '()\n')
                self.fd.write('{\n')
                self.indent(1), self.fd.write('FSM_LOGD("[' + self.current.class_name.upper() + '][LEAVING STATE ' + state.name + ']\\n");\n')
                self.emit_indented_code(state.leaving, 1)
                self.fd.write('}\n\n')

    def generate_variant_state_machine_definitions(self):
        self.generate_method_comment('Constructor. Calls enter() to set the initial state.')
        self.fd.write(self.current.class_name + '::' + self.current.class_name + '(' + self.current.extra_code.argvs + ')\n')
        if self.current.extra_code.cons != '':
            cons = self.current.extra_code.cons.strip().lstrip(',').strip()
            self.indent(1), self.fd.write(': ' + cons + '\n')
        self.fd.write('{\n')
        self.indent(1), self.fd.write('enter();\n')
        self.fd.write('}\n\n')

        self.fd.write('#if defined(MOCKABLE)\n')
        self.generate_method_comment('Virtual destructor (needed when MOCKABLE=virtual).')
        self.fd.write(self.current.class_name + '::~' + self.current.class_name + '() = default;\n')
        self.fd.write('#endif\n\n')

        self.generate_variant_enter_method_definition()

        self.fd.write('void ' + self.current.class_name + '::exit()\n{\n')
        self.emit_variant_thread_safety_lock(1)
        self.indent(1), self.fd.write('m_enabled = false;\n')
        self.fd.write('}\n\n')

        self.fd.write('bool ' + self.current.class_name + '::' + self.active_method_name() + '() const\n{\n')
        self.emit_variant_thread_safety_lock(1)
        self.indent(1), self.fd.write('return m_enabled;\n')
        self.fd.write('}\n\n')

        self.generate_variant_c_str_definition()
        self.generate_variant_event_method_definitions()
        self.generate_variant_transition_method_definitions()
        self.generate_variant_state_method_definitions()

    def generate_variant_state_machine_split(self, hpp_target, cpp_target):
        def emit_hpp():
            self.generate_variant_header(True)
            self.generate_namespace_begin()
            self.generate_variant_state_structs()
            self.generate_variant_state_machine_class_declaration()
            self.generate_namespace_end()
            self.generate_footer(True)

        emit_to_file(self, hpp_target, emit_hpp)

        def emit_cpp():
            self.generate_common_header()
            self.generate_include(0, '"', self.current.class_name + '.hpp', '"')
            self.fd.write('\n')
            self.generate_include(0, '<', 'cstdio', '>')
            self.generate_include(0, '<', 'cstring', '>')
            self.generate_include(0, '<', 'mutex', '>')
            self.generate_include(0, '<', 'optional', '>')
            self.generate_include(0, '<', 'type_traits', '>')
            self.generate_include(0, '<', 'utility', '>')
            self.generate_include(0, '<', 'variant', '>')
            self.fd.write('\n')
            self.generate_namespace_begin()
            self.method_comment_indent = 0
            self.generate_variant_state_machine_definitions()
            self.method_comment_indent = 4
            self.generate_namespace_end()

        emit_to_file(self, cpp_target, emit_cpp)

    def _state_is_check(self, state):
        """Return C++ expression: fsm.is<StateName>()."""
        return 'fsm.is<' + self.namespace_qualified(self.state_name(state)) + '>()'

    def generate_variant_unit_tests_header(self):
        self.generate_common_header()
        self.fd.write('#define MOCKABLE virtual\n')
        self.fd.write('#include "' + self.current.class_name + '.hpp"\n')
        self.fd.write('#include <gmock/gmock.h>\n')
        self.fd.write('#include <gtest/gtest.h>\n')
        self.fd.write('#include <cstring>\n\n')

    def generate_variant_unit_tests_mocked_class(self):
        self.generate_function_comment('Mocked state machine')
        self.fd.write('class ' + self.mock_class_name()
                      + ' : public ' + self.test_class_name())
        self.fd.write('\n{\npublic:\n')
        for origin, destination in list(self.current.graph.edges):
            tr = self.current.graph[origin][destination]['data']
            if tr.guard != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(bool, ')
                self.fd.write(self.guard_function(origin, destination))
                self.fd.write(', (), (override));\n')
            if tr.action != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(void, ')
                self.fd.write(self.transition_function(origin, destination))
                self.fd.write(', (), (override));\n')
        for node in list(self.current.graph.nodes):
            state = self.current.graph.nodes[node]['data']
            if state.entering != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(void, ')
                self.fd.write(self.state_entering_function(node, False))
                self.fd.write(', (), (override));\n')
            if state.leaving != '':
                self.indent(1)
                self.fd.write('MOCK_METHOD(void, ')
                self.fd.write(self.state_leaving_function(node, False))
                self.fd.write(', (), (override));\n')
        self.fd.write(self.current.extra_code.unit_tests)
        if self.current.extra_code.unit_tests != '':
            self.fd.write('\n')
        self.fd.write('};\n\n')

    def generate_variant_unit_tests_check_initial_state(self):
        self.generate_line_separator(0, ' ', 80, '-')
        self.fd.write('TEST(' + self.test_suite_name() + ', TestInitialState)\n{\n')
        self.indent(1)
        self.fd.write(self.test_class_name() + ' fsm; // Not mocked! Add constructor args if needed.\n')
        self.indent(1), self.fd.write('fsm.enter();\n\n')
        neighbors = [n for n in list(self.current.graph.neighbors('[*]'))
                     if n not in ['[*]', '*']]
        if len(neighbors) == 1:
            dest = neighbors[0]
            self.indent(1)
            self.fd.write('ASSERT_TRUE(' + self._state_is_check(dest) + ');\n')
            self.indent(1)
            self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + dest + '");\n')
        else:
            checks = ' || '.join([self._state_is_check(d) for d in neighbors])
            self.indent(1), self.fd.write('ASSERT_TRUE(' + checks + ');\n')
        self.fd.write('}\n\n')

    def generate_variant_unit_tests_check_cycles(self):
        count = 0
        for cycle in self.current.graph_cycles():
            self.generate_line_separator(0, ' ', 80, '-')
            self.fd.write('TEST(' + self.test_suite_name() + ', TestCycle'
                          + str(count) + ')\n{\n')
            count += 1
            self.indent(1)
            self.fd.write(self.mock_class_name() + ' fsm;\n')
            self.generate_mocked_guards(['[*]'] + cycle)
            self.fd.write('\n'), self.indent(1), self.fd.write('fsm.enter();\n')
            self.indent(1)
            self.fd.write('ASSERT_TRUE(' + self._state_is_check(cycle[0]) + ');\n')
            self.indent(1)
            self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[0] + '");\n')
            for i in range(len(cycle) - 1):
                tr = self.current.graph[cycle[i]][cycle[i + 1]]['data']
                if tr.event.name != '':
                    self.fd.write('\n'), self.indent(1)
                    self.fd.write('fsm.' + tr.event.caller('fsm') + ';\n')
                if i == len(cycle) - 2:
                    nxt = self.current.graph[cycle[i + 1]][cycle[1]]['data']
                    if nxt.event.name != '':
                        self.indent(1)
                        self.fd.write('ASSERT_TRUE(' + self._state_is_check(cycle[i + 1]) + ');\n')
                        self.indent(1)
                        self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i + 1] + '");\n')
                elif self.current.graph[cycle[i + 1]][cycle[i + 2]]['data'].event.name != '':
                    self.indent(1)
                    self.fd.write('ASSERT_TRUE(' + self._state_is_check(cycle[i + 1]) + ');\n')
                    self.indent(1)
                    self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + cycle[i + 1] + '");\n')
            self.fd.write('}\n\n')

    def generate_variant_unit_tests_pathes_to_sinks(self):
        count = 0
        for path in self.current.graph_all_paths_to_sinks():
            self.generate_line_separator(0, ' ', 80, '-')
            self.fd.write('TEST(' + self.test_suite_name() + ', TestPath'
                          + str(count) + ')\n{\n')
            count += 1
            self.indent(1), self.fd.write(self.mock_class_name() + ' fsm;\n')
            self.generate_mocked_guards(path)
            self.fd.write('\n'), self.indent(1), self.fd.write('fsm.enter();\n')
            for i in range(len(path) - 1):
                event = self.current.graph[path[i]][path[i + 1]]['data'].event
                if event.name != '':
                    self.fd.write('\n'), self.indent(1)
                    self.fd.write('fsm.' + event.caller() + ';\n')
                if i == len(path) - 2:
                    self.indent(1)
                    self.fd.write('ASSERT_TRUE(' + self._state_is_check(path[i + 1]) + ');\n')
                    self.indent(1)
                    self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + path[i + 1] + '");\n')
                elif self.current.graph[path[i + 1]][path[i + 2]]['data'].event.name != '':
                    self.indent(1)
                    self.fd.write('ASSERT_TRUE(' + self._state_is_check(path[i + 1]) + ');\n')
                    self.indent(1)
                    self.fd.write('ASSERT_STREQ(fsm.c_str(), "' + path[i + 1] + '");\n')
            self.fd.write('}\n\n')

    def generate_variant_unit_tests(self, cxxfile, files, separated):
        filename = self.current.class_name + self.tests_file_suffix()

        def emit():
            self.generate_variant_unit_tests_header()
            self.generate_variant_unit_tests_mocked_class()
            self.generate_variant_unit_tests_check_initial_state()
            self.generate_variant_unit_tests_check_cycles()
            self.generate_variant_unit_tests_pathes_to_sinks()
            if not separated:
                self.generate_unit_tests_main_function(filename, files)

        emit_to_file(self, os.path.join(os.path.dirname(cxxfile), filename), emit)

    def generate_variant_cxx_code(self, cxxfile, separated):
        generate_cpp20_backend(self, cxxfile, separated)

    ###########################################################################
    ### Entry point for translating a plantUML file into a C++ source file.
    ### param[in] uml_file: path to the plantuml file.
    ### param[in] cpp_or_hpp: generated a C++ source file ('cpp') or a C++ header file ('hpp').
    ### param[in] postfix: postfix name for the state machine name.
    ###########################################################################
    def format_generated_files(self, check_only=False):
        """Run clang-format on generated files, or fail if check mode finds drift."""
        formatter = shutil.which('clang-format')
        if formatter is None:
            self.fatal('clang-format was requested but not found in PATH')

        generated = sorted([p for p in Path(self.output_dir).iterdir()
                            if p.suffix in ('.hpp', '.cpp') and p.is_file()])
        if len(generated) == 0:
            return

        style_file = Path(__file__).resolve().parent.parent / '.clang-format'
        style_arg = '--style=file:' + str(style_file)

        if check_only:
            # For each generated file, compare on-disk content with what
            # clang-format would produce. Fail if any file would be changed.
            violations = []
            for file_path in generated:
                result = subprocess.run(
                    [formatter, style_arg, str(file_path)],
                    capture_output=True, text=True
                )
                with open(file_path, 'r') as fh:
                    original = fh.read()
                if result.stdout != original:
                    violations.append(str(file_path))
            if violations:
                msg = 'clang-format check failed (would reformat):\n  ' + '\n  '.join(violations)
                self.fatal(msg)
        else:
            for file_path in generated:
                try:
                    subprocess.run([formatter, style_arg, '-i', str(file_path)], check=True)
                except subprocess.CalledProcessError:
                    self.fatal('Formatting failed for generated file ' + str(file_path))

    def translate(self, uml_file, cpp_or_hpp, postfix, output_dir='.', snake_case=True,
                  namespace='', gen_mode='inline', clang_format_mode='off', thread_safe=False,
                  auto_flatten=False):
        """Parse one PlantUML file and generate target C++ artifacts end-to-end."""
        # Make the parser understand the plantUML grammar
        if self.parser == None:
            grammar_file = str(Path(__file__).resolve().with_name('statecharts.ebnf'))
            if not os.path.isfile(grammar_file):
                self.fatal('File path ' + grammar_file + ' does not exist!')
            try:
                with open(grammar_file, 'r') as grammar_stream:
                    grammar_text = grammar_stream.read()
            except OSError as ex:
                self.fatal('Failed loading grammar file ' + grammar_file +
                           ' for parsing plantuml statechart: ' + str(ex))
            try:
                self.parser = Lark(grammar_text)
            except Exception as ex:
                self.fatal('Failed parsing grammar file ' + grammar_file + ': ' + str(ex))
        # Make the parser read the plantUML file
        if not os.path.isfile(uml_file):
            self.fatal('File path ' + uml_file + ' does not exist!')
        # Reset per-translation mutable state so one Parser instance can be reused safely.
        self.tokens = []
        self.machines = dict()
        self.current = StateMachine()
        self.master = StateMachine()
        self.uml_file = uml_file
        self.output_dir = output_dir
        self.snake_case = snake_case
        self.namespace = namespace
        self.gen_mode = gen_mode
        self.thread_safe = thread_safe
        os.makedirs(self.output_dir, exist_ok=True)
        self.fd = open(self.uml_file, 'r')
        self.ast = self.parser.parse(self.fd.read())
        self.fd.close()
        if auto_flatten:
            self.auto_flatten_unsupported_diagram()
        self.assert_supported_diagram(auto_flatten=auto_flatten)
        # Create the main state machine
        self.current = StateMachine()
        self.current.name = Path(uml_file).stem
        self.current.class_name = self.fmt_name(self.current.name + postfix)
        self.current.enum_name = self.current.class_name + self.enum_suffix()
        self.master = self.current
        self.machines[self.current.name] = self.current
        # Traverse the AST to create the graph structure of the state machine
        # Uncomment to see AST: print(self.ast.pretty())
        for inst in self.ast.children:
            self.visit_ast(inst)
        # Do some operation on the state machine
        for self.current in self.machines.values():
            self.current.is_determinist()
            self.manage_noevents()
        # Generate the C++ code
        if cpp_or_hpp in ('cpp20', 'hpp20'):
            bare = 'hpp' if cpp_or_hpp == 'hpp20' else 'cpp'
            self.generate_variant_cxx_code(bare, False)
        else:
            self.generate_cxx_code(cpp_or_hpp, False)
        if clang_format_mode == 'format':
            self.format_generated_files(False)
        elif clang_format_mode == 'check':
            self.format_generated_files(True)
        # Generate the interpreted plantuml code
        self.generate_plantuml_file()

def main(argv=None):
    """Compatibility entry point delegating CLI behavior to `translator.cli`."""
    try:
        from .cli import run
    except ImportError:
        from cli import run
    run(Parser, argv)

if __name__ == '__main__':
    main()
