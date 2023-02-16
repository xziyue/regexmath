import itertools
from pyl3helper2.ast import *

l3_decl_prefix = [
    r'\cs_set:', r'\cs_gset:', r'\cs_new:', r'\cs_new_protected:'
]

l3_decl_suffix = [
    'Npn', 'Nn', 'cn', 'cpn', 'Npx', 'cpx', 'Nx', 'cx'
]

l3_decl_cs = []
for a, b in itertools.product(l3_decl_prefix, l3_decl_suffix):
    l3_decl_cs.append(a + b)

l3_data_types = [
    'int', 'box', 'prop', 'bool', 'seq',
    'tl', 'str', 'fp', 'clist', 'intarray', 'fparray', 'iow'
]

l3_def_prefix = [
    '\\:',  # local, public
    '\\::', # local, private
    '\\g:', # global, public
    '\\g::' # global, private
]

l3_data_types_lut = dict()

l3_def_cs = []
for dt in l3_data_types:
    for def_prefix in l3_def_prefix:
        l3_def_cs.append(def_prefix+dt)
        l3_data_types_lut[def_prefix+dt] = dt


def find_column(s, lexpos):
    line_start = s.rfind('\n', 0, lexpos) + 1
    return (lexpos - line_start) + 1


def find_get_line(s, lexpos):
    line_start = s.rfind('\n', 0, lexpos) + 1
    line_end = s.find('\n', line_start)
    if line_end == -1:
        return s[line_start:]
    else:
        return s[line_start:line_end]


class LaTeX3Parser:

    def __init__(self, lexer):
        self.lexer = lexer
        self.token_buffer = []
        self.in_func_body = False

        self.token_buf_size = 2
        self._init_token_buffer()

    def _init_token_buffer(self):
        for _ in range(self.token_buf_size):
            self.token_buffer.append(self.lexer.token())

    def raise_error(self, s):
        lexpos = self.peek_tok().lexpos
        lineno = self.peek_tok().lineno
        print(s)
        col_num = find_column(self.lexer.lexdata, lexpos)
        print('at line {}, column {}:'.format(lineno, col_num))
        print(find_get_line(self.lexer.lexdata, lexpos))
        print(' ' * (col_num - 1) + '^')
        exit(1)

    def is_tok_spacer(self, t, comment_is_spacer=True):
        if comment_is_spacer:
            return t.type in ('LINEBREAK', 'WHITESPACE', 'COMMENT')
        else:
            return t.type in ('LINEBREAK', 'WHITESPACE')

    def peek_tok(self):
        return self.token_buffer[0]

    def consume_tok(self):
        tok = self.token_buffer.pop(0)
        self.token_buffer.append(self.lexer.token())
        return tok

    def consume_until(self, type_or_types, exclude_spacer=True, make_ast_node=False):
        toks = []
        while True:
            next_tok = self.peek_tok()
            if not next_tok:
                self.raise_error(f'expected token of type "{type_or_types}", reaching EOF instead')

            is_next_of_type = False
            if isinstance(type_or_types, str):
                is_next_of_type = next_tok.type == type_or_types
            else:
                is_next_of_type = next_tok.type in type_or_types

            if is_next_of_type:
                if make_ast_node:
                    text = ''.join([x.value for x in toks])
                    if len(toks) == 0:
                        first_tok = None
                    else:
                        first_tok = toks[0]
                    return ASTTextStmtNode(text, first_tok)
                else:
                    return toks
            else:
                self.consume_tok()
                if exclude_spacer:
                    if self.is_tok_spacer(next_tok):
                        continue
                toks.append(next_tok)

    def consume_spacer(self, make_ast_node=False):
        toks = []
        while True:
            next_tok = self.peek_tok()
            if not next_tok:
                break

            if self.is_tok_spacer(next_tok):
                toks.append(self.consume_tok())
            else:
                break
        
        if make_ast_node:
            text = ''.join([x.value for x in toks])
            if len(toks) == 0:
                first_tok = None
            else:
                first_tok = toks[0]
            return ASTTextStmtNode(text, first_tok)
        else:
            return toks
    

    def match_tok(self, type_or_types):        
        next_tok = self.consume_tok()

        if not next_tok:
            self.raise_error(f'expected token of type "{type_or_types}", reaching EOF instead')
        
        if isinstance(type_or_types, str):
            if next_tok.type != type_or_types:
                self.raise_error(f'expected token of type "{type_or_types}", get type "{next_tok.type}" instead')
        else:
            if next_tok.type not in type_or_types:
                self.raise_error(f'expected token of type "{type_or_types}", get type "{next_tok.type}" instead')

        return next_tok


    def parse(self):
        ret = self.parse_EntityList()
        ret.parent = BaseASTNode()
        return ret
    
    def parse_EntityList(self):
        entity_list = []
        while True:
            
            if self.peek_tok() is None:
                break

            ret = self.parse_FuncDecl()
            if ret:
                entity_list.append(ret)
                continue
            
            ret = self.parse_StmtList()
            if ret:
                if ret.children_head is None:
                    break
                entity_list.append(ret)
                continue
        
        return build_entity_list_node(ASTEntityListNode, entity_list)

    def parse_StmtList(self):
        stmt_list = []
        while True:
            ret = self.parse_Stmt()
            if ret is None:
                break
            if isinstance(ret, ASTTextStmtNode) and len(ret.text) == 0:
                break # we encountered an empty statement
            stmt_list.append(ret)
        
        return build_entity_list_node(ASTStmtListNode, stmt_list)

    def parse_GetNameStmt(self):
        assert self.peek_tok().type == 'CS'
        if self.peek_tok().value == r'\:getname':
            statements = []
            statements.append(ASTCSStmtNode(self.consume_tok()))
            statements.append(self.consume_spacer(True))
            cs = ASTCSStmtNode(self.match_tok('CS'))
            statements.append(cs)
            
            node = build_entity_list_node(ASTGetNameStmtNode, statements)
            node.components['cs'] = cs
            return node
        return None

    def parse_DefStmt(self):
        assert self.peek_tok().type == 'CS'
        if self.peek_tok().value in l3_def_cs:

            statements = []
            def_cs = ASTCSStmtNode(self.consume_tok())
            statements.append(def_cs)
            statements.append(self.consume_spacer(True))
            cs = ASTCSStmtNode(self.match_tok('CS'))
            statements.append(cs)

            scope = 'local'
            if def_cs.tok.value[1] == 'g':
                scope = 'global'
            data_type = l3_data_types_lut[def_cs.tok.value]
            private = False
            if def_cs.tok.value.startswith('\\::') or def_cs.tok.value.startswith('\\g::'):
                private = True
            
            node = build_entity_list_node(ASTDefStmtNode, statements)
            node.components['def_cs'] = def_cs
            node.components['cs'] = cs
            node.metadata['scope'] = scope
            node.metadata['data_type'] = data_type
            node.metadata['private'] = private
            return node
        return None

    def parse_GroupStmt(self):
        self.match_tok('LBRACE')
        entity_list_node = self.parse_EntityList()
        self.match_tok('RBRACE')

        node = ASTGroupStmtNode(entity_list_node.children_head)
        for child in node.iter_children():
            child.parent = node

        return node

    def parse_Stmt(self):
        if self.peek_tok() is None:
            return None

        if self.peek_tok().type == 'LBRACE':
            return self.parse_GroupStmt()
        if self.peek_tok().type == 'COMMENT':
            tok = self.consume_tok()
            return ASTCommentStmtNode(tok)
        if self.peek_tok().type == 'CS':
            ret = self.parse_DefStmt()
            if ret:
                return ret
            
            ret = self.parse_GetNameStmt()
            if ret:
                return ret
            
            tok = self.peek_tok()
            if tok.value in l3_decl_cs:
                return None # this is no longer a generic statement (it is a function declaration)
            
            self.consume_tok()
            return ASTCSStmtNode(tok)
        if self.peek_tok().type in ('ARG', 'TEXARG'):
            return self.parse_ArgStmt()
        
        # now, we are left with other statements
        first_tok = self.peek_tok()
        stmt_text = ''
        while True:
            next_tok = self.peek_tok()
            if not next_tok:
                break
            if self.is_tok_spacer(next_tok, False) or next_tok.type in ('OTHER', 'SCS'):
                stmt_text += next_tok.value
                self.consume_tok()
            else:
                break
        
        return ASTTextStmtNode(stmt_text, first_tok)

    def parse_ArgStmt(self):
        tok = self.match_tok(('ARG', 'TEXARG'))
        node = ASTArgStmtNode(tok)
        node.metadata['type'] = arg_tok_type_lut[tok.type]
        node.metadata['level'] = tok.value.count('#')
        return node

    def parse_FuncArgList(self):
        if self.peek_tok().type in ('ARG', 'TEXARG'):
            arg_list = []
            while True:
                tok = self.peek_tok()
                if not tok:
                    break
                if tok.type in ('ARG', 'TEXARG'):
                    arg_list.append(self.parse_ArgStmt())
                else:
                    break
            
            return build_entity_list_node(ASTFuncArgListNode, arg_list)
        
        return None

    def parse_FuncDecl(self):
        next_tok = self.peek_tok()
        if next_tok.value in l3_decl_cs:
            statements = []
            decl_cs = ASTCSStmtNode(self.consume_tok())
            statements.append(decl_cs)
            
            # acquire the cs (could be a CS token or a GroupStmt)
            statements.append(self.consume_spacer(True))
            if self.peek_tok().type == 'CS':
                cs = ASTCSStmtNode(self.match_tok('CS'))
            else:
                cs = self.parse_GroupStmt()

            if cs is None:
                self.raise_error('expected CS/GroupStmt in FuncDecl')

            statements.append(cs)

            statements.append(self.consume_spacer(True))

            arg_list = self.parse_FuncArgList() # nullable
            if arg_list:
                statements.append(arg_list)
            
            statements.append(self.consume_until('LBRACE', make_ast_node=True))
            # parse the group stmt
            self.in_func_body = True
            func_body = self.parse_GroupStmt()
            self.in_func_body = False

            if not func_body:
                self.raise_error('expected FuncBody in function declaration')

            statements.append(func_body)

            node = build_entity_list_node(ASTFuncDeclNode, statements)
            node.components['decl_cs'] = decl_cs
            node.components['cs'] = cs
            node.components['arg_list'] = arg_list
            node.components['func_body'] = func_body

            return node
        
        return None
    