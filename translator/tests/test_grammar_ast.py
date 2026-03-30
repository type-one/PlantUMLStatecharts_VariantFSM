from pathlib import Path

from lark import Lark


def _assert_ast_structure(root):
    # The 'start' rule now directly contains all children.
    assert root.data == 'start'
    assert len(root.children) == 21
    c = 0

    assert root.children[c].data == 'comment'
    c += 1

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

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 3
    assert root.children[c].children[0] == '[*]'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State1'
    c += 1

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 3
    assert root.children[c].children[0] == 'State1'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State2'
    c += 1

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State2'
    assert root.children[c].children[1] == '->'
    assert root.children[c].children[2] == 'State3'
    assert root.children[c].children[3].data == 'uml_action'
    assert len(root.children[c].children[3].children) == 1
    assert root.children[c].children[3].children[0] == '/ action = 1/3'
    c += 1

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State3'
    assert root.children[c].children[1] == '<-'
    assert root.children[c].children[2] == 'State4'
    assert root.children[c].children[3].data == 'guard'
    assert len(root.children[c].children[3].children) == 1
    assert root.children[c].children[3].children[0] == '[a[0] + b[] + c(3)]'
    c += 1

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

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State5'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State6'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 2
    assert root.children[c].children[3].children[0] == 'setpoint'
    assert root.children[c].children[3].children[1] == '(x, y)'
    c += 1

    assert root.children[c].data == 'transition'
    assert len(root.children[c].children) == 4
    assert root.children[c].children[0] == 'State6'
    assert root.children[c].children[1] == '-->'
    assert root.children[c].children[2] == 'State7'
    assert root.children[c].children[3].data == 'event'
    assert len(root.children[c].children[3].children) == 3
    assert root.children[c].children[3].children[0] == 'foo'
    assert root.children[c].children[3].children[1] == 'bar'
    assert root.children[c].children[3].children[2] == '()'
    c += 1

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

    # Preserve current grammar behavior for this known malformed split.
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
    grammar = (repo_root / 'translator' / 'statecharts.ebnf').read_text()
    source = (repo_root / 'translator' / 'tests' / 'grammar.plantuml').read_text()

    parser = Lark(grammar)
    ast = parser.parse(source)

    assert ast.data == 'start'
    _assert_ast_structure(ast)
