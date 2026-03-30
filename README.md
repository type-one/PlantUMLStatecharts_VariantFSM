# PlantUML Statecharts (State Machine) Translator

A Python3 tool parsing [PlantUML statecharts](https://plantuml.com/fr/state-diagram)
scripts and generating C++ code with its unit tests.

The original C++11 version is hosted in [Lecrapouille/Statecharts](https://github.com/Lecrapouille/Statecharts).
This modded version is hosted in [type-one/PlantUMLStatecharts_VariantFSM](https://github.com/type-one/PlantUMLStatecharts_VariantFSM) and supports both C++11 and C++20 `std::variant` FSM generation.

This repository contains:
- A single C++11 header file containing the base code for defining a state
  machine. You can use it to define manually your own state machines. The code
  is [here](include/state_machine.hpp).
- A single C++20 header file containing helpers for `std::variant` /
  `std::visit` generated state machines. The code is
  [here](include/state_machine_variant.hpp).
- A Python3 script reading [PlantUML
  statecharts](https://plantuml.com/fr/state-diagram) and generating Statecharts
  (aka finite state machines or FSM) in either:
  - C++11 class-based code inheriting from the base state machine runtime.
  - C++20 `std::variant` / `std::visit` code in a self-contained generated class.
  The code is [here](translator/statecharts.py).
- Several [examples](examples) of PlantUML statecharts are given.

The Python script offers you:
- To generate code in a compromise between simplicity to read, no virtual
  methods, memory footprint, and no usage of external lib (such
  [boost](https://github.com/boost-ext/sml) lib).
- To do some basic verification to check if your state machine is well
  formed.
- To generate C++ unit tests (using [Google
  tests](https://github.com/google/googletest)) to verify if your state machine
  is functional.
- The goal of this tool is to separate things: one part is to manage the logic of
  how a state machine shall work (the base class), and the second part is to write
  code in a descriptive way (the child class).

Here is an example of PlantUML code source, generating this kind of diagram,
this tool is able to parse (Click on the figure to see the PlantUML code source):

[![Gumball](doc/Gumball.png)](examples/Gumball.plantuml)

This repository also contains several more evolved
[examples](examples/README.md) of statecharts the tool can parse. For people not
sure how state machines work, there are several links explaining them given
in the last section of this document.

## Limitation: what the tools cannot offer to you

- Generate only C++ code. You can help contributing to generate other languages.
- The tool only parses simple finite state machines. Hierarchical, orthogonal,
  concurrent, composite, fork/join, pseudo-states, and history are not
  supported.
  The unsupported diagrams kept as references are listed in
  [examples/README.md](examples/README.md).
- For FSM, the `do / activity` and `after(X ms)` are not yet managed.
- Does not manage multi-edges (several transitions from the same origin and
  destination state). As consequence, you cannot add several `on event` in the
  same state.
- I am not a UML expert, so probably this tool does not follow strictly UML
  standards. This tool has not yet been used in real production code.
- Does not offer formal proof to check if your output transitions from a state
  are mutually exclusive or if some branches are not reachable. This is currently
  too complex for me to develop (any help is welcome): we need to parse and
  understand C++ code. For example, in the previous [diagram](doc/RichMan.png),
  if the initial count of quarters starts with a negative value, you will be stuck in
  the state `CountQuarter`. In the same idea: events on output transitions shall
  be mutually exclusive but the tool cannot parse C++ logic. And finally for
  unit tests, to help generate good values
- Does not give 100% of compilable C++ code source. It depends on the code of
  your guards and actions. It should be simple valid C++ code. The main code of
  the generated state machine is functional you do not have to modify it but you
  may have to clean a little the code for your guards, actions, add member
  variables to complete the compilation.

### Compile-safe stubs for unresolved callbacks

The generator automatically emits a `TODO` stub for every bare function call
found in transition actions, state entry/exit snippets, or guard expressions
that is **not** already covered by an auto-generated method or a user-supplied
`'[code]` block.  The stub has the form:

```cpp
template<typename... Args>
void beep(Args&&...) { /* TODO: implement callback from PlantUML action/state code. */ }
```

This keeps the generated output in a **compilable state** even when the PlantUML
diagram references functions that have not been written yet, so you can compile
and run unit tests incrementally.

**Limits — what stubs do NOT cover:**

- **Undeclared variables** referenced inside guard expressions or actions (e.g.
  `min`, `hours` in a guard `[min == 0 && hours == 0]`) are *not* auto-stubbed.
  They are not function calls, so the extractor cannot detect them.  You must
  add the corresponding member-variable declarations yourself in a `'[code]`
  block of the diagram, or directly inside the generated class.
- **Stubs use a variadic template** so they accept any argument list, but they
  do nothing at runtime.  Replace each stub with a real implementation before
  shipping to production.
- Stubs are placed in the *client-code section* of the generated class (between
  the `// --- user-defined code ---` markers).  They will not conflict with
  methods you add by hand later.

## Prerequisite

- Python3 and the following packages:
  - [Lark](https://github.com/lark-parser/lark) a parsing toolkit for Python. It
    is used for reading PlantUML files.
  - [Networkx](https://networkx.org/) before the PlantUML is translated into C++
    file, a directed graph structure is created as an intermediate structure before
    generating the C++ code (shall be ideally a MultiDiGraph).
- [PlantUML](https://plantuml.com) called by the Makefile to generate PNG pictures
  of examples but it is not used by our Python3 script.
- C++ compiler:
  - For `cpp` / `hpp` generation: a C++14 (or newer) compiler.
  - For `cpp20` / `hpp20` generation: a C++20 compiler.

On Debian/Ubuntu Linux (system-wide packages):
```
sudo apt install python3-lark python3-networkx
```

Or using pip (any platform / virtual environment):
```
python3 -m pip install networkx lark
```

## Command line

```
./statecharts.py <plantuml statechart file> <langage> [name] [-o output_dir] [-s|--snake] [-c|--camel] [-n namespace] [--auto-flatten]
```

Where:
- `plantuml statechart file` is the path of the [PlantUML
   statecharts](https://plantuml.com/fr/state-diagram) file as input.  This repo
   contains [examples](examples/input).
- `langage` is one of:
  - `"cpp"` to generate C++11 class-based source file.
  - `"hpp"` to generate C++11 class-based header file.
  - `"hpp20"` to generate a self-contained C++20 `std::variant` / `std::visit` header file (all-in-one).
  - `"cpp20"` to generate a C++20 `std::variant` / `std::visit` header **and** a matching `.cpp` implementation stub (split mode).
- `name` is optional and allows giving a postfix to the C++ class name and file.
- `-o output_dir` is optional and redirects all generated files (`.cpp`/`.hpp`,
  test files, interpreted `.plantuml`) to the given folder.
- `-s` / `--snake` enables `snake_case` naming for generated C++ identifiers
  (class names, method names, enum values, file names, mock/test class names).
  This is the default mode.
- `-c` / `--camel` switches naming to `CamelCase`.
- `-n namespace` / `--namespace namespace` is optional and wraps the generated
  class in the given C++ namespace (e.g. `-n myapp` or `-n com::acme`).  The
  generated unit-test file adds a matching `using namespace ::myapp;` directive.
- `--auto-flatten` is optional and attempts to flatten hierarchical/composite
  state blocks into a flat FSM before generation.
  Current limits: orthogonal/concurrent regions (`--` / `||`) are still not
  supported and will still fail fast with a non-zero exit.
  Each composite state must also define an internal initial transition of the
  form `[*] -> SubState`; otherwise flattening fails early because the active
  leaf state cannot be derived unambiguously.

Current repository examples with `--auto-flatten`:
- `SimpleComposite.plantuml`: generates and compiles in both `cpp` and `cpp20`.
- `ComplexComposite.plantuml`: generates and compiles in both `cpp` and `cpp20`.
- `Pompe.plantuml`: still fails early because one composite state does not
  declare an internal initial transition `[*] -> SubState`.
- `SimpleOrthogonal.plantuml`: still fails early because orthogonal/concurrent
  regions are not flattened yet.

Example:
```
./statecharts.py foo.plantuml cpp controller
```

Will create a `foo_controller.cpp` file with a class name `foo_controller`
(default `snake_case`).

Generate a self-contained C++20 header:
```
./statecharts.py foo.plantuml hpp20 controller
```

Will create a `foo_controller.hpp` file using `std::variant` and `std::visit`.

Generate split C++20 header + implementation stub:
```
./statecharts.py foo.plantuml cpp20 controller
```

Creates `foo_controller.hpp` (full definition) and `foo_controller.cpp` (stub).

Generate into a specific output directory:
```
./statecharts.py foo.plantuml hpp20 controller -o ../build/generated

Attempt auto-flattening of hierarchical composites before generation:
```
./statecharts.py examples/SimpleComposite.plantuml cpp20 --auto-flatten -o ../build/generated
```
```

Generate with `snake_case` naming convention and a C++ namespace:
```
./statecharts.py foo.plantuml hpp20 -s -n myapp
```

Creates `foo.hpp` with `class foo` inside `namespace myapp { ... }`, and
`foo_tests.cpp` with `class mock_foo` and `TEST(foo_tests, ...)` entries.

Will create generated files in `../build/generated`.

Typical C++20 compilation command:
```
g++ --std=c++20 -Wall -Wextra -Iinclude -I. -o FooApp main.cpp
```

Where `main.cpp` includes your generated header:
```
#include "FooController.hpp"
```

Typical C++20 unit-test compilation command (generated `FooControllerTests.cpp`):
```
g++ --std=c++20 -Wall -Wextra -Iinclude -I. \
  FooControllerTests.cpp `pkg-config --cflags --libs gtest gmock` \
  -o FooControllerTests
```

## Runtime compile-time macros

The runtime headers support the following optional macros:

- `FSM_DEBUG`: enables runtime trace logging through `FSM_LOGD(...)` in both
  [include/state_machine.hpp](include/state_machine.hpp) and
  [include/state_machine_variant.hpp](include/state_machine_variant.hpp).
- `FSM_LOGE(...)`: emits error logs to `stderr`.

Example:

```bash
g++ --std=c++14 -DFSM_DEBUG -Iinclude ...
```

Thread safety is now selected at generation time with `--thread-safe`. Without
that option, generated code contains no mutex member and no locking code.

Typical C++20 build with thread safety enabled:

```bash
./statecharts.py path/to/foo.plantuml hpp20 controller -o build/generated --thread-safe
g++ --std=c++20 -Wall -Wextra -pthread \
  -Iinclude -Ibuild/generated main.cpp -o build/FooApp
```

Typical C++20 generated unit-test build with thread safety enabled:

```bash
./statecharts.py path/to/foo.plantuml cpp20 controller -o build/generated --thread-safe
g++ --std=c++20 -Wall -Wextra -pthread \
  -Iinclude -Ibuild/generated \
  build/generated/foo_controller.cpp \
  build/generated/foo_controller_tests.cpp \
  `pkg-config --cflags --libs gtest gmock` \
  -o build/FooControllerTests
```

On Linux and other POSIX platforms, `-pthread` is typically required when
thread-safe code is generated with `--thread-safe`.

## Style and lint compliance (.clang-format / .clang-tidy)

This repository now supports three complementary workflows:

1. Format/check template source files maintained in the repo.
2. Format/check generated C++ files directly from the generator CLI.
3. Run `clang-tidy` on generated code using a compile database.

Format template input files (headers/sources under `include/`, `examples/`, `translator/`):

```bash
bash tools/format_templates.sh
```

Check template input files in CI (fails on style drift):

```bash
bash tools/check_templates_format.sh
```

Format generated C++ files immediately after generation:

```bash
./translator/statecharts.py path/to/foo.plantuml cpp20 controller -o build/generated --clang-format
```

Check generated C++ files formatting without modifying them:

```bash
./translator/statecharts.py path/to/foo.plantuml cpp20 controller -o build/generated --check-clang-format
```

Run `clang-tidy` on generated code:

- `clang-tidy` needs a `compile_commands.json` compile database.
- You can produce one with your normal build system (CMake), or with `bear` for Make-based builds.

Example with `bear`:

```bash
bear --output build/compile_commands.json -- make -C examples -j8
clang-tidy -p build/compile_commands.json build/generated/foo_controller.cpp
clang-tidy -p build/compile_commands.json build/generated/foo_controller.hpp
```

Tip: because `.clang-tidy` has `WarningsAsErrors: "*"`, running tidy in CI is a good gate for both template and generated code quality.

## Compile Examples

```
cd examples
make -j8
```

Examples are compiled into the `build` folder as well as their PNG file.
You can run binaries. For example:
```
./build/Gumball
```

## PlantUML Statecharts syntax

This tool does not pretend to parse the whole PlantUML syntax or implement the
whols UML statecharts standard. Here is the basic PlantUML statecharts syntax it
can understand:
- `FromState --> ToState : event [ guard ] / action`
- `FromState -> ToState : event [ guard ] / action`
- `ToState <-- FromState : event [ guard ] / action`
- `ToState <- FromState : event [ guard ] / action`
- `State : entry / action`
- `State : exit / action`
- `State : on event [ guard ] / action` Where `[ guard ]` is optional.
- `'` for single-line comment.
- The statecharts shall have one `[*]` as a source.
- Optionally `[*]` as a sink.

- Note: `[ guard ]` and `/ action` are optional. You can add C++ code (the less
  the better, you can complete with `'[code]` as depicted in this section). The
  tool shall manage spaces between tokens `-->`, `:`, `[]`, and `/`. The `event`
  is optional it can be spaced but shall refer to a valid C++ syntax of a
  function (so do not add logic operations).

Note: I added some sugar syntax:
- `State : entering / action` alias for `State : entry / action`.
- `State : leaving / action` alias for `State : exit / action`.
- `State : comment / description` to add a C++ comment for the state in the
  generated code.
- `\n--\n action` alias for `/ action` to follow State-Transition Diagrams used
  in [Structured Analysis for Real
  Time](https://academicjournals.org/journal/JETR/article-full-text-pdf/07144DC1419)
  (but also to force carriage return on PlantUML diagrams).

I added some syntax to help generate extra C++ code. They start with the `'`
keyword which is a PlantUML single-line comment so they will not produce syntax
error when PlantUML is parsing the file but, on our side, we exploit them.
- `'[brief]` for adding a comment for the generated state machine class.
- `'[header]` for adding code in the header of the file, before the class of the
  state machine. You can include other C++ files, and create or define functions.
- `'[footer]` for adding code in the footer of the file, after the class of the
  state machine.
- `'[param]` are arguments to pass to the state machine C++ constructor. Commas
  are added. One argument by line.
- `'[cons]` to allow init the argument before the code of the constructor.
  One argument by line.
- `'[init]` is C++ code called by the constructor or bu the `reset()` function.
- `'[code]` to allow you to add member variables or member functions.
- `'[test]` to allow you to add C++ code for unit tests.

## State machines and Statecharts

The State/Transition Diagram (STD) from the Structured Analysis for Real-Time
methodology and the UML statechart share similar notation but differ in where
actions are attached: in STD, actions belong exclusively to transitions, whereas
in UML, actions can be attached to both transitions and states.

The distinction traces back to 1956, when two complementary formalisms were
defined: **Moore machines**, in which actions are associated with states, and
**Mealy machines**, in which actions are associated with transitions.  Both
formalisms describe the same class of systems and can be translated into each
other without loss of expressiveness
[cite](https://www.itemis.com/en/yakindu/state-machine/documentation/user-guide/overview_what_are_state_machines).
In 1984, Harel unified the two models and extended them with composite states,
orthogonal regions, and history, naming the result *statecharts*.  UML later
adopted statecharts as its standard behavioural diagram.

Some code generators (such as the one described in this
[paper](https://cs.emis.de/LNI/Proceedings/Proceedings07/TowardEfficCode_3.pdf))
normalise the statechart into a pure Mealy graph before emitting code.  This
translator deliberately does not perform that normalisation: actions on both
states and transitions are preserved in the generated output so that the
resulting C++ code stays close to the original diagram.

A related distinction worth noting is the difference between an **action** and
an **activity**.  An action is instantaneous — it completes without consuming
modelled time.  An activity, by contrast, runs concurrently with the system and
can be preempted by any event the state reacts to; it is halted when the state
is exited or when the activity itself finishes.  Consequently, an activity
should not be driven by a periodic `update` event, because its body is not
meant to be repeated.

The order of execution of actions across transitions and states is detailed in
the next section.

## Rule of execution in Statecharts

Let's suppose the C++ code of the following state machine has been generated with
the C++ name class `Simple`.

![alt statemachine](doc/Simple.png)

- The system `Simple` is entering to `State1` (made active): the `action7` is
  called (private method of the class `Simple` or any local function).
- The external `event3` (public method of the class `Simple` or any local
  function) may occur and when this will happen, and if and only if the `guard3`
  returns `true` (boolean expression of a function returning a boolean), then the
  `action3` is called (method of the class `Simple` or any local function).
- If `event1` is triggered and if the `guard1` returns `true` then the system is
  leaving the `State1` and the exit `action8` is called followed by the
  transition `action1`.
- The system is entering `State2` (made active): the `action9` is called.
- `event5` may be triggered and once happening the `action5` is called.
- If `event2` is triggered then the `State2` exit `action10` is called. Else if
  `event6` is triggered then the `State2` exit `action10` is called.
- Note: when `event3` or `event5` are triggered, the entry and exit actions of
  the corresponding state is not called.
- An activity is started after the entry action and halted before the exit
  action.

If an output transition has no explicit event and no guard is given (or if the guard
is returning true) and the activity has finished then the transition is
immediately made in an atomic way. In our example, if `event1`, `event2`, and
`guard1` were not present this would create an infinite loop.

Events shall be mutually exclusive since we are dealing in discrete time events,
several events can occur during the delta time but since in this API you have to
call the event and the state machine reacts immediately, the order is defined by
the caller.

## Details Design

### Translation pipeline

The translation pipeline of the Python script is the following:
- The [Lark](https://github.com/lark-parser/lark) parser loads the
  [grammar](translator/statecharts.ebnf) file and parses the PlantUML statechart
  input.  The grammar is not derived from an official PlantUML source (PlantUML
  does not publish a formal grammar); it covers the subset of the syntax this
  tool supports.
- The parsed input produces a Lark Abstract Syntax Tree (AST).
- The AST is visited and a directed graph ([Networkx](https://networkx.org/)
  `DiGraph`) is built: nodes are states, arcs are transitions, events and
  actions are stored as arc attributes.
- The graph is then traversed for validation (reachability, well-formedness)
  and finally for code generation.  Unit tests are generated from graph cycles
  and paths from the initial state to sink states, exercising the transitions
  that lead to each reachable state.

### State matrix representation

A state machine, like any directed graph, can be represented as a sparse
transition matrix.  For example, the motor controller:

![alt motor](doc/Motor.png)

maps to the following table (guards and actions omitted for clarity):

|                 | Set Speed  | Halt      | --        |
|-----------------|------------|-----------|-----------|
| IDLE            | STARTING   |           |           |
| STOPPING        |            |           | IDLE      |
| STARTING        | SPINNING   | STOPPING  |           |
| SPINNING        | SPINNING   | STOPPING  |           |

- The first column holds source states.
- The first row holds events.  The `--` column represents an eventless
  (automatic) transition: the state transitions immediately without waiting for
  an event.
- Each cell holds the destination state; empty cells are ignored transitions.

Both C++ backends encode this matrix, but with different mechanisms.

### C++11 implementation (`cpp` / `hpp`)

The generated class inherits from the CRTP base class
`state_machine<Derived, STATES_ID>` provided by
[include/state_machine.hpp](include/state_machine.hpp).

Key design points:
- **State enumeration**: states are identified by values of an external `enum
  STATES_ID`.  Two mandatory sentinel values — `IGNORING_EVENT` and
  `CANNOT_HAPPEN` — model holes in the transition matrix.
- **State table**: a private fixed-size `std::array` holds one `state` struct
  per state.  Each struct carries function pointers for the entering, leaving,
  and internal-event actions.
- **Transition table**: each public event method defines a local static
  `std::map<STATES_ID, transition>` (the sparse row for that event).  Each
  `transition` struct carries the destination state, a guard function pointer,
  and an action function pointer.
- **Dispatch**: events delegate to a single private `transit()` method in the
  base class, which evaluates the guard, calls exit/action/entry callbacks in
  the correct UML order, and updates the active state.
- **Mutual exclusion**: the UML norm requires events to be mutually exclusive.
  Thread-safe generation (`--thread-safe`) adds a `std::mutex` and wraps every
  public method with `std::unique_lock`; otherwise locking is a no-op.
- The design is inspired by
  [State Machine Design in C++](https://www.codeproject.com/Articles/1087619/State-Machine-Design-in-Cplusplus-2)
  with the following differences: the curiously recurring template pattern (CRTP)
  is used in place of virtual dispatch; internal and external transitions share
  a single `transit()` method; an internal event queue is included; and guards
  and actions are placed on transitions rather than on states.

### C++20 `std::variant` implementation (`cpp20` / `hpp20`)

The generated class is **self-contained** — it does not inherit from any base
class.  It only includes
[include/state_machine_variant.hpp](include/state_machine_variant.hpp), which
provides the `fsm::overloaded` visitor helper.

Key design points:
- **State tags**: each state is represented by a distinct empty struct
  (e.g. `struct state1{};`, `struct state2{};`).  These act as type-level
  discriminants with zero runtime overhead.
- **Current state**: stored as `std::variant<state1, state2, ...> m_state`.
  The active state is the type currently held by the variant; no integer index
  or enum is needed at the application level.
- **Event dispatch**: each public event method calls
  `std::visit(fsm::overloaded{ ... }, m_state)`.  The `fsm::overloaded` helper
  (a variadic lambda aggregator) routes execution to the lambda matching the
  active state type.  States that do not react to a given event are covered by
  a no-op default lambda.  There is no runtime lookup table; the compiler can
  resolve the dispatch at compile time.
- **Guards and actions**: per-transition private methods follow the naming
  convention `on_guarding_<src>_<dst>()` (returns `bool`) and
  `on_transitioning_<src>_<dst>()` (returns `void`).  All are declared
  `MOCKABLE` so unit-test mocks can override them without subclassing the full
  FSM.
- **Entry and exit actions**: private methods `on_entering_<state>()` and
  `on_leaving_<state>()`, also `MOCKABLE`.
- **State change**: a transition assigns the destination tag value to `m_state`
  (e.g. `m_state = state2{};`), replacing the current variant alternative.
- **Thread safety**: the `--thread-safe` flag adds a `mutable std::mutex
  m_mutex` member and wraps every public method (events, `is()`, `c_str()`,
  `is_active()`) with `std::lock_guard<std::mutex>`.
- **Output modes**:
  - `hpp20` produces a single self-contained header (declarations and
    definitions in one file).
  - `cpp20` produces a split pair: `<name>.hpp` with declarations and
    `<name>.cpp` with method bodies.

## References

### State machines and statecharts

- [Yakindu statecharts](https://www.itemis.com/en/yakindu/state-machine/documentation/user-guide/overview_what_are_state_machines)
  YAKINDU Statechart Tools is a tool for specializing and developing state machines.
- [Developing Reactive Systems Using Statecharts](http://msdl.cs.mcgill.ca/people/hv/teaching/MoSIS/lectures/StatechartsModellingAndSimulation.pdf)
  A course on statecharts modelling and simulation.
- [Modeling dynamic system views](http://niedercorn.free.fr/iris/iris1/uml/uml09.pdf)
  A French-language introduction to UML statecharts.
- [ML/SysML state diagram and Arduino programming](https://eduscol.education.fr/sti/ressources_pedagogiques/umlsysml-diagramme-detat-et-programmation-arduino#fichiers-liens)
  A French-language statecharts course with open source code covering advanced
  features such as activities and history.
- [State Machine Design in C++](https://www.codeproject.com/Articles/1087619/State-Machine-Design-in-Cplusplus-2)
  The C++11 state machine runtime in this repository is inspired by this project.
- [Towards Efficient Code Synthesis from Statecharts](https://cs.emis.de/LNI/Proceedings/Proceedings07/TowardEfficCode_3.pdf)
  Research paper on generating state machine code from statecharts.
- [Real-Time Structured Methods: Systems Analysis](https://www.amazon.com/Real-Time-Structured-Methods-Analysis-Engineering/dp/0471934151)
  by Keith Edwards, Wiley 1993.  SART can be seen as a precursor to UML, using
  three complementary diagram types: data-transformation diagrams (discrete and
  continuous), control-flow diagrams (enabling/disabling/triggering processes),
  and state-transition diagrams linking the two.
- [Structured Analysis for Real Time](https://www.espacetechnologue.com/wp-content/uploads/2017/03/2_DeveloppementApp_STRv11.pdf)
- [UML Behavioral Diagrams: State Transition Diagram](https://youtu.be/OsmWASXE2IM) and
  [State Transition Diagram](https://youtu.be/PF9QcYWIsVE) YouTube videos made by the
  Georgia Tech Software Development Process.

### C++20 `std::variant` / `std::visit` FSMs

- [`std::variant` — cppreference](https://en.cppreference.com/w/cpp/utility/variant)
  The C++ standard reference for the discriminated union type used to hold the
  active state in the C++20 backend.
- [`std::visit` — cppreference](https://en.cppreference.com/w/cpp/utility/variant/visit)
  The C++ standard reference for the visitor dispatch mechanism, including the
  canonical `overloaded` lambda-aggregator pattern used in this generator.
- [Finite State Machines in C++17 with `std::variant`](https://www.cppstories.com/2023/finite-state-machines-variant-cpp/)
  by Bartłomiej Filipek.  Walks through building a variant-based FSM step by
  step; the dispatch structure is conceptually equivalent to what this generator
  emits.
- [std::variant and the Overload Pattern](https://www.modernescpp.com/index.php/visiting-a-std-variant-with-the-overload-pattern/)
  by Rainer Grimm.  Explains the `overloaded` helper in detail, covering
  deduction guides and the `using` pack expansion that makes multi-lambda
  `std::visit` calls compile.
- [P0088 — Variant: a type-safe union (final proposal)](https://www.open-std.org/jtc1/sc22/wg21/docs/papers/2016/p0088r3.html)
  The ISO C++ committee paper that introduced `std::variant` into C++17, by
  Axel Naumann.  Useful background on the design rationale and the
  `valueless_by_exception` guarantee.
