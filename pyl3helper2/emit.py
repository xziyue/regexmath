# semantic check + code emission
from pyl3helper2.ast import *
from pyl3helper2.parser import l3_def_cs, l3_data_types_lut, find_column
import copy
import string

default_func_identifiers = []
default_func_identifiers.extend(l3_def_cs)
assert '\:getname' not in default_func_identifiers
default_func_identifiers.append('\:getname')



@dataclass
class IdentifierDef:
    parent: ASTFuncDeclNode
    type: str # variable, reserved
    var_type: str # type if is variable
    name: str # this is the name variable (literally)
    scope: str
    private: bool
    latex_name : str = None # this is the name of the declared latex3 variable

    def __eq__(self, o):
        return self.parent is o.parent and self.name == o.name
    

def ast_iterator(node):
    yield node

    for child in node.iter_children():
        for item in ast_iterator(child):
            yield item

def ast_stmt_iterator(node):
    yield node

    for child in node.iter_children():
        if isinstance(child, ASTStmtListNode):
            for item in ast_iterator(child):
                yield item

class LaTeX3Emitter:

    def __init__(self, pkg_name, src):
        self.pkg_name = pkg_name
        self.ast = None
        self.src = src

        self.func_stack = [] # the current function stack

        self.global_def = [] # list of global definitions
        self.def_statements = [] # list of all definition statements
        self.func_decls = [] # list of all function declarations

        self.func_name_set = set()
        

        # add default decl to global definition
        for idt in default_func_identifiers:
            # add global definitions for the "keywords"
            self.global_def.append(
                IdentifierDef(
                    parent=None,
                    type='reserved',
                    var_type=None,
                    name=idt,
                    scope='global',
                    private=False,
                    latex_name=None
                )
            )


    @staticmethod
    def indent_text(text, size):
        new_lines = []
        for line in text.split('\n'):
            if len(line) > 0:
                new_lines.append(' ' * size + line)
            else:
                new_lines.append(line)
        return '\n'.join(new_lines)
        
    # convert a number to latex style number
    @staticmethod
    def to_latex_num(num):
        res = ''
        while num > 0:
            q, r = divmod(num, 26)
            res += string.ascii_lowercase[r]
            num = q

        return str(reversed(res))

    # convert a function name into latex style function name
    # this is used to name variables associated with functions
    def get_l3_func_name(self, func_node):
        suggested_name = None
        cs = func_node.components['cs']
        if isinstance(cs, ASTCSStmtNode):
            suggested_name = cs.tok.value[1:]
        elif isinstance(cs, ASTGroupStmtNode):
            suggested_name = self.pkg_name + '_' + cs.emit()[1:-1]
        else:
            raise RuntimeError('invalid CS type')
        
        valid_string = string.ascii_letters + '_'
        suggested_name = ''.join([x if x in valid_string else '_' for x in suggested_name])

        if suggested_name in self.func_name_set:
            ind = 0
            while True:
                new_name = suggested_name + '_' + self.to_latex_num(ind)
                if new_name not in self.func_name_set:
                    suggested_name = new_name
                    break
                ind += 1
        
        self.func_name_set.add(suggested_name)
        return suggested_name


    def emit_variable_declarations_from_def_entities(self, def_entities):
        if len(def_entities) == 0:
            return ''
        
        def1s, def2s = list(zip(*def_entities))
        def1_pad = len(max(def1s, key=len))

        lines = []
        for i in range(len(def1s)):
            lines.append(def1s[i].ljust(def1_pad) + def2s[i])
        
        return '\n'.join(lines)


    # this is used to emit the variable declarations
    def emit_variable_declarations(self, defs):
        def_entities = []
        for var in defs:
            if var.type == 'variable':
                line = '\\{}_new:N'.format(
                    var.var_type
                )
                if var.latex_name is None:
                    latex_name = '\\{}{}{}_{}_{}'.format(
                            'g' if var.scope=='global' else 'l',
                            '__' if var.private else '_',
                            self.pkg_name if var.parent is None else var.parent.metadata['latex_name'],
                            var.name.lstrip('\\').lstrip(':'), var.var_type)
                    var.latex_name = latex_name
                line += ' ' + var.latex_name
                def1 = line

                if var.parent is not None:
                    def2 = '  % :pyl3helper VARIABLE {} FROM {}'.format(var.name, var.parent.metadata['debug_name'])
                else:
                    def2 = '  % :pyl3helper GLOBAL VAR {}'.format(var.name)
                def_entities.append((def1, def2))
        return def_entities

    def repr_function_stack(self):
        return '->'.join([repr(x.metadata['debug_name']) for x in self.func_stack])

    def raise_error(self, s):
        func_stack = self.func_stack
        print(f'an error occurred: {s}')
        if func_stack is None:
            func_stack = []
        if len(func_stack) > 0:
            print(f'function chain:', self.repr_function_stack())
            
        exit(1)

    # check func stack recursively to find the identifier
    def find_identifier(self, name):
        assert isinstance(name, str)
        # check if already defined globally
        for d in self.global_def:
            if d.name == name:
                return d

        # check in function stack to see if defined locally
        for func_decl in self.func_stack:
            for d in func_decl.metadata['local_def']:
                if d.name == name:
                    return d
        
        return None

    def add_identifier_to_list(self, id, def_list):
        id_find = self.find_identifier(id.name)
        if id_find:
            raise self.raise_error(f'identifier "{id.name}" already defined: {id_find}')
        def_list.append(id)

    # scan variable definition in a EntityList and add them to def_list
    # this only scan recursively into ASTStmtList nodes
    def scan_and_add_variable_definitions(self, node, parent, def_list):
        assert isinstance(node, ASTEntityListNode)
        for child in ast_stmt_iterator(node):
            if isinstance(child, ASTDefStmtNode):
                assert child.components['cs'].tok.value.startswith('\\')
                self.def_statements.append(child)
                # add them to local definitions
                self.add_identifier_to_list(
                    IdentifierDef(
                        parent,
                        'variable',
                        child.metadata['data_type'],
                        child.components['cs'].tok.value,
                        child.metadata['scope'],
                        child.metadata['private'],
                        None
                    ),
                    def_list
                )

    def preprocess_func_decl(self, ast_node):
        assert isinstance(ast_node, ASTFuncDeclNode)
        
        self.func_stack.append(ast_node)
        # generate latex function name for this function
        l3_func_name = self.get_l3_func_name(ast_node)
        ast_node.metadata['latex_name'] = l3_func_name
        ast_node.metadata['debug_name'] = ast_node.components['cs'].emit()
        ast_node.metadata['func_stack'] = copy.copy(self.func_stack)
        
        # check if function declaration type is correct
        decl_cs_sig = ast_node.components['decl_cs'].tok.value.partition(':')[2]
        if decl_cs_sig[0] == 'N':
            if not isinstance(ast_node.components['cs'], ASTCSStmtNode):
                self.raise_error('invalid CS name for N type function declaration')
        elif decl_cs_sig[0] == 'c':
            if not isinstance(ast_node.components['cs'], ASTGroupStmtNode):
                self.raise_error('invalid CS name for c type function declaration')
        else:
            self.raise_error('invalid function declarator')

        # check arg validity
        if 'p' not in decl_cs_sig:
            if ast_node.components['arg_list'] is not None:
                self.raise_error('this function does not accept any arguments')


        # build arg lut
        if ast_node.components['arg_list'] is not None:
            assert isinstance(ast_node.components['arg_list'], ASTFuncArgListNode)
            
            all_args = list(ast_node.components['arg_list'].iter_children())
            assert len(all_args) > 0
            if len(all_args) > 9:
                self.raise_error('LaTeX only allows at most 9 arguments')

            arg_types = set()
            # do not allow the mix use of TEXARG and ARG
            for arg in all_args:
                assert isinstance(arg, ASTArgStmtNode)
                arg_types.add(arg.metadata['type'])
            
            if len(arg_types) > 1:
                self.raise_error('cannot mix numbered arguments and named arguments')

            arg_type = arg_types.pop()
            if arg_type == TeXArgType.TEXT:
                # build the LUT
                arg_lut = dict()
                for arg_id, arg in enumerate(all_args):
                    level = arg.metadata['level']
                    arg_lut[arg.tok.value] = '#' * level + repr(arg_id + 1)

                ast_node.metadata['arg_lut'] = arg_lut

                # change the parameters back to numeric LaTeX arguments
                for arg in all_args:
                    arg.replace(ASTEmitTextNode(arg_lut[arg.tok.value]))

        # scan for variable definitions in the function body
        ast_node.metadata['local_def'] = []
        self.scan_and_add_variable_definitions(ast_node.components['func_body'], ast_node, ast_node.metadata['local_def'])

        # process recursive function definitions
        self.scan_and_process_function(ast_node.components['func_body'])
        
        self.func_stack.pop()
        return ast_node


    def scan_and_process_function(self, node):
        assert isinstance(node, ASTEntityListNode)
        for child in node.iter_children():
            if isinstance(child, ASTFuncDeclNode):
                self.preprocess_func_decl(child)
                self.func_decls.append(child)
            elif isinstance(child, ASTEntityListNode) and not isinstance(child, ASTFuncDeclNode):
                self.scan_and_process_function(child)

    def process_and_emit(self, ast):
        # add global pass for scanning def\get name

        assert isinstance(ast, ASTEntityListNode)
        self.ast = ast

        # scan for global variable definitions
        self.scan_and_add_variable_definitions(ast, None, self.global_def)

        # pre-process functions
        self.scan_and_process_function(self.ast)

        # # after definition scanning, all definition statements can be deleted
        # for stmt in self.def_statements:
        #     if stmt.next is not None:
        #         if isinstance(stmt.next, ASTTextStmtNode):
        #             if len(stmt.next.text.strip()) == 0:
        #                 stmt.next.erase()
        #     stmt.erase()

        # after definition scanning, all definition statements should be commented

        for stmt in self.def_statements:
            new_stmt = ASTEmitTextNode('%  ' + stmt.emit())
            stmt.replace(new_stmt)

        assert len(self.func_stack) == 0
        replace_pairs = []
        # now, we need to replace argument parameters
        for func_decl in self.func_decls:
            if 'arg_lut' in func_decl.metadata:
                arg_lut = func_decl.metadata['arg_lut']
                for node in ast_iterator(func_decl.components['func_body']):
                    if isinstance(node, ASTArgStmtNode):
                        if node.metadata['type'] == TeXArgType.TEXT and node.tok.value in arg_lut:
                            new_node = ASTEmitTextNode(arg_lut[node.tok.value])
                            replace_pairs.append((node, new_node))

        for node, new_node in replace_pairs:
            node.replace(new_node)


        assert len(self.func_stack) == 0
        # after argument parameters replacement, we need to check if there is any argument left
        for func_decl in self.func_decls:
            # recover the function stack for debug output
            self.func_stack = func_decl.metadata['func_stack']
            for node in ast_iterator(func_decl.components['func_body']):
                if isinstance(node, ASTArgStmtNode):
                    if node.metadata['type'] == TeXArgType.TEXT:
                        self.raise_error(f'undefined argument "{node.tok.value}"')
            self.func_stack = []
        assert len(self.func_stack) == 0

        # scan for global definition insertion point
        global_def_loc_node = None
        for node in ast_iterator(self.ast):
            if isinstance(node, ASTCommentStmtNode):
                if node.tok.value.strip() == '%%GLOBAL_DEF%%':
                    global_def_loc_node = node
                    break
        
        if global_def_loc_node is None:
            self.raise_error('unable to find global definition insertion point, please make to indicate it with "%%GLOBAL_DEF%%"')

        # emit global variables
        global_def_emit = self.emit_variable_declarations_from_def_entities(self.emit_variable_declarations(self.global_def))
        global_def_text = '%%GLOBAL_DEF%%\n' + global_def_emit + '\n%%END_GLOBAL_DEF%%'
        global_def_text = self.indent_text(global_def_text, find_column(self.src, global_def_loc_node.tok.lexpos) - 1)
        global_def_node = ASTEmitTextNode(global_def_text + '\n')
        global_def_loc_node.replace(global_def_node)


        # for each function, determine a chain of declaration emit
        for func in self.func_decls:
            func.metadata['emit_func'] = []
        for func in self.func_decls:
            func.metadata['func_stack'][0].metadata['emit_func'].append(func)
        # now, insert variable declarations for functions
        for func in self.func_decls:
            # determine indent level
            indent_level = find_column(self.src, func.components['decl_cs'].tok.lexpos) - 1
            lines = []

            # information about function names
            lines.append('% :pyl3helper FUNCTION DECLARATION: ' + func.metadata['debug_name'])
            lines.append('% :pyl3helper VARIABLE DECLARATION PREFIX: ' + func.metadata['latex_name'])

            def_entities = []
            for emit_func in func.metadata['emit_func']:
                def_entities.extend(self.emit_variable_declarations(emit_func.metadata['local_def']))
            
            # variable definitions
            var_lines = self.emit_variable_declarations_from_def_entities(def_entities)
            if len(var_lines) > 0:
                for line in var_lines.split('\n'):
                    lines.append(line)

            # information about argument translation
            if 'arg_lut' in func.metadata:
                for key, val in func.metadata['arg_lut'].items():
                    lines.append('% :pyl3helper ARG TRANSLATION: {} => {}'.format(key, val))

            longest_line = len(max(lines, key=len))
            lines.insert(0, '% :pyl3helper {}'.format('FUNCTION HEADER'.center(longest_line, '-')))
            lines.append('% :pyl3helper {}'.format('END FUNCTION HEADER'.center(longest_line, '-')))

            func_header = '\n'.join(lines)
            func_header = '\n' + self.indent_text(func_header, indent_level) + '\n' + ' ' * indent_level
            func_header_node = ASTEmitTextNode(func_header)
            func.prepend(func_header_node)


        # finally, perform variable replacement
        replace_pairs = []
        assert len(self.func_stack) == 0
        for func_decl in self.func_decls:
            self.func_stack = func_decl.metadata['func_stack']
            for node in ast_stmt_iterator(func_decl.components['func_body']):
                if isinstance(node, ASTCSStmtNode):
                    if node.tok.value.startswith('\\:'):
                        # try to find the declaration
                        idt = self.find_identifier(node.tok.value)
                        if idt is None:
                            self.raise_error(f'unable to find identifier {node.tok.value}')
                        if idt.type == 'reserved':
                            self.raise_error(f'encountered an invalid identifier {node.tok.value}')
                        new_node = ASTEmitTextNode(idt.latex_name)
                        replace_pairs.append((node, new_node))

            self.func_stack = []

        # replace global variables too
        for node in ast_stmt_iterator(self.ast):
            if isinstance(node, ASTCSStmtNode):
                if node.tok.value.startswith('\\:'):
                    # try to find the declaration
                    idt = self.find_identifier(node.tok.value)
                    if idt is None:
                        self.raise_error(f'unable to find identifier {node.tok.value}')
                    if idt.type == 'reserved':
                        self.raise_error(f'encountered an invalid identifier {node.tok.value}')
                    new_node = ASTEmitTextNode(idt.latex_name)
                    replace_pairs.append((node, new_node))

        for node, new_node in replace_pairs:
            node.replace(new_node)

        return self.ast






        
                    
                    

        
        


