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