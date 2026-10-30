"""编译各阶段共享的数据结构：Token、AST 节点，以及 C 子集的类型描述。

这些类型描述服务于 VM 的自定义 ABI，实际字节大小由 codegen.type_size 决定。
"""

from typing import Any
from dataclasses import dataclass

@dataclass
class Token:
    """词法单元；line 是从 1 开始的源代码行号，宏展开时保留使用位置。"""
    tktype : str
    value  : Any
    line   : int

@dataclass
class ASTNode:
    """children 存子表达式/语句，metas 存名称、类型或作用域，约定见 docs/AST.txt。"""
    nodeType : str
    children : list[Any]
    metas    : tuple[Any]

@dataclass
class C_Basetype:
    typename : str

@dataclass
class C_Pointer:
    oftype   : Any

@dataclass
class C_Array:
    """dimension 按声明顺序记录各维长度；下标运算依此计算行优先的元素大小。"""
    oftype    : Any
    dimension : tuple[int]

@dataclass
class C_Func:
    rettype   : Any
    argtype   : list[tuple] # list[(C_Type,var_name)]

@dataclass
class C_Struct:
    fields   : list[tuple] # list[(C_Type,var_name)]

@dataclass
class C_Union:
    fields   : list[tuple] # list[(C_Type,var_name)]

@dataclass
class C_Enum:...

@dataclass
class C_Var:
    """符号表中的变量包装；oftype 才是其值类型，不代表多一层 C 指针。"""
    oftype   : Any

@dataclass
class C_Const:
    oftype   : Any
    value    : Any

@dataclass
class C_Metatype:
    typename : str

@dataclass
class C_Typedef:
    of : Any
