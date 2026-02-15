from common import Token,ASTNode

class Ref:
    def __init__(self,val):
        self.val = val

def parse(tokens: list[Token]) -> ASTNode:
    idx_ref = Ref(0)
    return program(idx_ref,tokens)

def program(idx_ref: Ref,tokens: list[Token]) -> ASTNode:
    children = []
    this = ASTNode("program",children)
    
    

    return this