from pyl3helper2.lexer import LatexLexer, letter_regex_doc, letter_regex_code
from pyl3helper2.parser import LaTeX3Parser
from pyl3helper2.emit import LaTeX3Emitter, ast_iterator
import os
import click

my_dir = os.path.dirname(__file__)

lexer = LatexLexer()


@click.command()
@click.argument('input')
@click.option('-n', '--package-name', default='mypkg', help='package name')
@click.option('-N', '--package-name-upper', default='MyPkg', help='package name (upper case)')
@click.option('-o', '--output', default=None, help='output filename')
def main(**kwargs):
    inp = kwargs['input']
    pkg_name = kwargs['package_name']
    pkg_name_upper = kwargs['package_name_upper']
    out = kwargs['output']

    assert os.path.exists(inp)
    with open(inp) as infile:
        src = infile.read()

    # global preprocessing
    src = src.replace('@@@@', pkg_name_upper)
    src = src.replace('@@', pkg_name)

    lexer.lexer.input(src)
    parser = LaTeX3Parser(lexer.lexer)
    ast = parser.parse()

    emitter = LaTeX3Emitter(pkg_name, src)
    res = emitter.process_and_emit(ast)

    if out is None:
        print(res)
    else:
        with open(out, 'w') as outfile:
            outfile.write(res.emit())


if __name__ == '__main__':
    main()
