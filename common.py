from typing import Any
from dataclasses import dataclass

@dataclass
class Token:
    tktype : str
    value  : Any
    line   : int

@dataclass
class ASTNode:
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
class C_Metatype:
    typename : str