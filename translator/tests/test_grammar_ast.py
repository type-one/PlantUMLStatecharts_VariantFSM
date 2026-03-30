"""
AST shape contract tests.

These tests parse ``grammar.plantuml`` — the dedicated fixture diagram that
exercises every grammar production — and assert the exact shape of the Lark
parse-tree that comes out.  The purpose is to act as a canary: any change
to ``statecharts.ebnf`` that alters the tree structure will be caught here
before it silently breaks code-generation.
"""

from pathlib import Path

from lark import Lark


def _assert_ast_structure(root):
    """Walk the parse-tree produced from grammar.plantuml and assert
    every node in document order.

    The function uses a running index ``c`` rather than hardcoded constants
    so that inserting a new assertion group is cheap and the intent of each
    group remains legible.
    """
    # The 'start' rule flattens all top-level statements into one children list.
    assert root.data == 'start'
    assert len(root.children) == 21
    c = 0

    # ---- Inline comment node ---------------------------------------------------
    assert root.children[c].data == 'comment'
    c += 1

    # ---- cpp directive nodes --------------------------------------------------
    # [header] / [footer] / [init] / [code] directives carry verbatim C++ text
    # that is injected into the generated files at the corresponding location.

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[header]'
    assert root.children[c].children[1].strip() == 'this is a header 1'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[header]'
    assert root.children[c].children[1].strip() == 'this is a header 2'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[footer]'
    assert root.children[c].children[1].strip() == 'this is a footer 1'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[footer]'
    assert root.children[c].children[1].strip() == 'this is a footer 2'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[init]'
    assert root.children[c].children[1].strip() == 'a = 0;'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[init]'
    assert root.children[c].children[1].strip() == 'b = "ff";'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[code]'
    assert root.children[c].children[1].strip() == 'int foo();'
    c += 1

    assert root.children[c].data == 'cpp'
    assert len(root.children[c].children) == 2
    assert root.children[c].children[0] == '[code]'
    assert root.children[c].children[1].strip() == 'virtual std::string foo(std::foo<Bar> const& arg[]) = 0;'
    c += 1

    # ---- Simple transitions (source --> target, no label) --------------------
    # Both arrow syntax variants (-- and -) must produce identical 3-child nodes.

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 3
    assert root.children[c].children[0] == '[*]'   # pseudo-initial state
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State1'
    c += 1

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 3
    assert root.children[c].children[0] == 'State1'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State2'
    c += 1

    # ---- Transition with action (/ ...) ---------------------------------------
    # The action text keeps the leading '/' so the generator can strip it.

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State2'
    assert root.children[c].children[1] == '->'   # short-dash form
    assert root.children[c].children[2] == 'State3'
    assert root.children[c].children[3].data == 'uml_action'
    assert len(root.children[c].children[3].children) == 1
    assert root.children[c].children[3].children[0] == '/ action = 1/3'  # '/' inside value is kept verbatim
    c += 1

    # ---- Transition with guard ([...]) ----------------------------------------
    # Square-bracket content is parsed verbatim including nested brackets.

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State3'
    assert root.children[c].children[1] == '<-'   # reversed arrow
    assert root.children[c].children[2] == 'State4'
    assert root.children[c].children[3].data == 'guard'
    assert len(root.children[c].children[3].children) == 1
    assert root.children[c].children[3].children[0] == '[a[0] + b[] + c(3)]'  # nested '[]' kept intact
    c += 1

    # ---- Transition with both guard and action --------------------------------

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 5
    assert root.children[c].children[0] == 'State4'
    assert root.children[c].children[1] == '<--'
    assert root.children[c].children[2] == 'State5'
    assert root.children[c].children[3].data == 'guard'
    assert len(root.children[c].children[3].children) == 1
    assert root.children[c].children[3].children[0] == '[a[0] + b[] + c(3)]'
    assert root.children[c].children[4].data == 'uml_action'
    assert len(root.children[c].children[4].children) == 1
    assert root.children[c].children[4].children[0] == '/ action = 1/3'
    c += 1

    # ---- Transitions with named events ----------------------------------------
    # An event node contains: event-name [namespace] [argument-list].
    # Namespace ("foo bar") and argument list "()" are separate children.

    # event with argument list only
    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State5'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State6'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 2
    assert root.children[c].children[3].children[0] == 'setpoint'  # event name
    assert root.children[c].children[3].children[1] == '(x, y)'    # arg list
    c += 1

    # event with namespace qualifier ("foo bar") but no guard/action
    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State6'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State7'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 3
    assert root.children[c].children[3].children[0] == 'foo'   # namespace
    assert root.children[c].children[3].children[1] == 'bar'   # event name
    assert root.children[c].children[3].children[2] == '()'    # empty arg list
    c += 1

    # event + action (action text contains function calls and string literals)
    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 5
    assert root.children[c].children[0] == 'State8'
    assert root.children[c].children[1] == '<-'
    assert root.children[c].children[2] == 'State7'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 2
    assert root.children[c].children[3].children[0] == 'foo'
    assert root.children[c].children[3].children[1] == 'bar'
    assert root.children[c].children[4].data == 'uml_action'
    assert len(root.children[c].children[4].children) == 1
    assert root.children[c].children[4].children[0] == '/ foo(a, 2[]) + "bar"; gg'
    c += 1

    # event + guard
    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 5
    assert root.children[c].children[0] == 'State9'
    assert root.children[c].children[1] == '<-'
    assert root.children[c].children[2] == 'State8'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 2
    assert root.children[c].children[3].children[0] == 'foo'
    assert root.children[c].children[3].children[1] == 'bar'
    assert root.children[c].children[4].data == 'guard'
    assert len(root.children[c].children[4].children) == 1
    assert root.children[c].children[4].children[0] == '[a[0] + b[] + c(3)]'
    c += 1

    # ---- Malformed guard/action split (known edge-case) -----------------------
    # When the guard text itself contains a '/' the grammar cannot distinguish
    # the guard-end from the action-start, so the slash and everything after it
    # spills into a second uml_action node.  This behaviour is intentional and
    # pinned here so any grammar change that accidentally fixes *or breaks* it
    # is caught immediately.
    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 6
    assert root.children[c].children[0] == 'State10'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State9'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 2
    assert root.children[c].children[3].children[0] == 'foo'
    assert root.children[c].children[3].children[1] == 'bar'
    assert root.children[c].children[4].data == 'guard'
    assert root.children[c].children[4].children[0] == '[a[0] + b[] + c(3)] / foo(a, a[2]'
    assert root.children[c].children[5].data == 'uml_action'
    assert root.children[c].children[5].children[0] == '/ 2) + "bar"; gg'
    c += 1

    # ---- state_block (nested / composite state) --------------------------------
    # A ``state X { ... }`` block becomes a 'state_block' node whose first child
    # is the state name and whose remaining children are the inner transitions.

    assert root.children[c].data == 'state_block'
    assert len(root.children[c].children) == 4
    assert str(root.children[c].children[0]) == 'State11'

    c0 = root.children[c].children[1]
    assert c0.data == 'transition'
    assert len(c0.children) == 3
    assert c0.children[0] == '[*]'
    assert c0.children[1] == '->'
    assert c0.children[2] == 'ON'

    c1 = root.children[c].children[2]
    assert c1.data == 'transition'
    assert len(c1.children) == 4
    assert c1.children[0] == 'ON'
    assert c1.children[1] == '->'
    assert c1.children[2] == 'OFF'
    assert c1.children[3].data == 'event'
    assert len(c1.children[3].children) == 1
    assert c1.children[3].children[0] == 'off'

    c2 = root.children[c].children[3]
    assert c2.data == 'transition'
    assert len(c2.children) == 4
    assert c2.children[0] == 'OFF'
    assert c2.children[1] == '->'
    assert c2.children[2] == 'ON'
    assert c2.children[3].data == 'event'
    assert len(c2.children[3].children) == 1
    assert c2.children[3].children[0] == 'on'


def test_grammar_ast_shape(repo_root: Path):
    """Parse grammar.plantuml directly with Lark and assert the full tree shape.

    This test instantiates the grammar from ``statecharts.ebnf`` and parses
    the dedicated fixture file ``grammar.plantuml``, which was written to
    exercise every production rule at least once.  The resulting Lark tree is
    then passed to ``_assert_ast_structure`` which walks every node in document
    order and checks:

    * The rule name (``node.data``) matches the expected production.
    * The child count matches.
    * Leaf values (state names, arrow tokens, verbatim text, etc.) are
      preserved exactly as they appear in the source diagram.

    Expectations:
    - Root is ``start`` with exactly 21 direct children.
    - 1 comment, 8 cpp directives (2×header, 2×footer, 2×init, 2×code).
    - 11 transition nodes covering all arrow variants, guard/action combos,
      named events with namespaces and argument lists, reversed arrows, and
      the known malformed guard/action split edge case.
    - 1 state_block (composite state) with 3 inner transitions.
    """
    grammar = (repo_root / 'translator' / 'statecharts.ebnf').read_text()
    source = (repo_root / 'translator' / 'tests' / 'grammar.plantuml').read_text()

    parser = Lark(grammar)
    ast = parser.parse(source)

    assert ast.data == 'start'
    _assert_ast_structure(ast)
