from typing import Any
from dataclasses import dataclass

@dataclass
class Token:
    tktype : str
    value  : Any
    line   : int