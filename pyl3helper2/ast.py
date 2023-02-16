from dataclasses import dataclass
from ply.lex import LexToken
from typing import Any
from enum import Enum, auto

class NotImplementedError(Exception):
    pass

class TeXArgType(Enum):
    NUMERIC = auto()
    TEXT = auto()

arg_tok_type_lut = dict(
    TEXARG=TeXArgType.NUMERIC,
    ARG=TeXArgType.TEXT
)


# global variables
print_fn = print
level_counter = 0
max_detail_show_length = 40

class BaseASTNode():

    def emit(self):
        raise NotImplementedError()

    def show(self):
        raise NotImplementedError()

    def _get_show_prefix(self):
        assert level_counter >= 0
        return '-' + '--' * level_counter

    def _show_node(self, node):
        s = self._get_show_prefix()
        s += node.__class__.__name__
        internal_data = node.emit()
        if len(internal_data) > max_detail_show_length:
            internal_data = internal_data[:max_detail_show_length] + '...'
        internal_data = internal_data.replace('\n', '\\n').replace('\r', '\\r')
        
        print_fn('{} ({})'.format(s, internal_data))



class ASTNode(BaseASTNode):

    def __post_init__(self):
        self.parent = None
        self.prev = None
        self.next = None

    def iter_children(self):
        return iter(())

    def erase(self):
        if self.prev is not None:
            self.prev.next = self.next
        if self.next is not None:
            self.next.prev = self.prev
        
        # a special case for ASTEntityListNode
        if isinstance(self.parent, ASTEntityListNode):
            if self.parent.children_head is self:
                self.parent.children_head = self.next

        self.parent = None
        self.prev = None
        self.next = None

    def replace(self, node):
        if self.prev is not None:
            self.prev.next = node
        if self.next is not None:
            self.next.prev = node

        # a special case for ASTEntityListNode
        if isinstance(self.parent, ASTEntityListNode):
            if self.parent.children_head is self:
                self.parent.children_head = node
        
        node.parent = self.parent
        node.prev = self.prev
        node.next = self.next

        self.parent = None
        self.prev = None
        self.next = None
    
    def prepend(self, node):
        assert isinstance(node, ASTNode)
        node.parent = self.parent

        old_prev = self.prev
        old_next = self.next

        if old_prev is not None:
            old_prev.next = node
        node.prev = old_prev
        node.next = self
        self.prev = node

        # a special case for ASTEntityListNode
        if isinstance(self.parent, ASTEntityListNode):
            if self.parent.children_head is self:
                self.parent.children_head = node

    def append(self, node):
        assert isinstance(node, ASTNode)
        node.parent = self.parent

        old_prev = self.prev
        old_next = self.next

        if old_next is not None:
            old_next.prev = node
        node.prev = self
        node.next = old_next
        self.next = node

    def show(self):
        # by default, this node should not print anything
        return



@dataclass
class ASTEntityListNode(ASTNode):
    children_head : Any = None

    def iter_children(self):
        head = self.children_head
        if head is None:
            return iter(())
        while head is not None:
            yield head
            head = head.next

    def emit(self):
        for x in self.iter_children():
            assert x.parent is self
        return ''.join([x.emit() for x in self.iter_children()])

    def show(self):
        global level_counter
        s = self._get_show_prefix() + self.__class__.__name__
        print_fn(s)
        level_counter += 1
        for child in self.iter_children():
            if isinstance(child, ASTEntityListNode):
                child.show()
            else:
                self._show_node(child)
        level_counter -= 1


class ASTStmtListNode(ASTEntityListNode):
    pass

@dataclass
class ASTTextStmtNode(ASTNode):
    text: str # merged text statement
    first_tok: LexToken # used to keep track of the location of this statement

    def emit(self):
        return self.text


@dataclass
class ASTSingleTokNode(ASTNode):
    tok: LexToken

    def emit(self):
        return self.tok.value

@dataclass
class ASTCommentStmtNode(ASTSingleTokNode):
    pass

@dataclass
class ASTCSStmtNode(ASTSingleTokNode):
    pass

@dataclass
class ASTArgStmtNode(ASTSingleTokNode):

    def __post_init__(self):
        super().__post_init__()
        self.metadata = dict()


@dataclass
class ASTGroupStmtNode(ASTEntityListNode):

    def emit(self):
        return '{' + super().emit() + '}'


@dataclass
class ASTFuncDeclNode(ASTEntityListNode):

    def __post_init__(self):
        super().__post_init__()
        self.components = dict(
            decl_cs=None,
            cs=None,
            arg_list=None,
            func_body=None
        )

        self.metadata = dict()


@dataclass
class ASTFuncArgListNode(ASTEntityListNode):
    pass


@dataclass
class ASTDefStmtNode(ASTEntityListNode):

    def __post_init__(self):
        super().__post_init__()
        self.components = dict(
            def_cs=None,
            cs=None,
        )

        self.metadata = dict()

@dataclass
class ASTGetNameStmtNode(ASTEntityListNode):
    
    def __post_init__(self):
        super().__post_init__()
        self.components = dict(
            cs=None
        )

    # the emit function of this node should never be used...
    # this node needs to be replaced with a text node in the future


# this is a node inserted by post-processor
@dataclass
class ASTEmitTextNode(ASTNode):
    text: str

    def emit(self):
        return self.text


# build an entity list node from a set of orphaned children
# note that this entity list node will not have a parent
def build_entity_list_node(list_class, nodes, parent=None):
    obj = list_class()
    assert isinstance(obj, ASTEntityListNode)
    if len(nodes) > 0:
        obj.children_head = nodes[0]
        obj.children_head.parent = obj
        current_node = obj.children_head
        for node in nodes[1:]:
            current_node.append(node)
            current_node = node
    
    obj.parent = parent
    return obj
