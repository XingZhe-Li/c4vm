from common import *

class Ref:
    def __init__(self,val):
        self.val = val

class SymTable:
    mapper : dict
    father : "SymTable"

    def __init__(self,mapper = None,father = None):
        if mapper == None:
            self.mapper = {}
        else:
            self.mapper = mapper
        self.father = father
    def get(self,sym):
        if sym in self.mapper and self.mapper is not None:
            return self.mapper[sym]
        if self.father:
            return self.father.get(sym)
    def set(self,sym,val):
        self.mapper[sym] = val
    def derive(self):
        return SymTable(father=self)

def parse(tokens: list[Token]) -> ASTNode:
    idx = Ref(0)
    return program(idx,tokens)

def tools(idx: Ref, tokens: list[Token]) -> tuple:
    # tool functions for pattern matching
    def peek():
        if idx.val < len(tokens):
            return tokens[idx.val]
        return None

    def match(tktype=None,value=None):
        tk = peek()
        if tktype is not None and tktype != tk.tktype: return None
        if value  is not None and value  != tk.value:  return None
        idx.val += 1
        return tk

    def peekN(n: int):
        res = []
        for didx in range(n):
            if idx.val + didx < len(tokens):
                res.append(tokens[idx.val + didx])
            else:
                res.append(None)
        return res

    def matchN(lst: list):
        # [(tktype,value)]
        res = []
        for didx,(tktype,value) in enumerate(lst):
            if idx.val + didx < len(tokens):
                if tktype is not None and tktype != tokens[idx.val + didx].tktype:
                    return None 
                if value  is not None and value  != tokens[idx.val + didx].value:
                    return None
                res.append(tokens[idx.val + didx])
            else:
                return None
        idx.val += len(lst)
        return res

    return peek,match,peekN,matchN

def rootTable() -> SymTable:
    symtable = SymTable({
        ("char",):("type",C_Basetype("char")),
        ("short",):("type",C_Basetype("short")),
        ("int",):("type",C_Basetype("int")),
        ("long",):("type",C_Basetype("long")),
        ("long","long"):("type",C_Basetype("long long")),

        ("signed",):("type",C_Basetype("signed")),
        ("unsigned",):("type",C_Basetype("unsigned")),

        ("float",):("type",C_Basetype("float")),
        ("double",):("type",C_Basetype("double")),
        
        ("unsigned","char"):("type",C_Basetype("char")),
        ("unsigned","short"):("type",C_Basetype("unsigned short")),
        ("unsigned","int"):("type",C_Basetype("unsigned int")),
        ("unsigned","long"):("type",C_Basetype("unsigned long")),
        ("unsigned","long","long"):("type",C_Basetype("unsigned long long")),

        ("signed","char"):("type",C_Basetype("signed char")),
        ("signed","short"):("type",C_Basetype("signed short")),
        ("signed","int"):("type",C_Basetype("signed int")),
        ("signed","long"):("type",C_Basetype("signed long")),
        ("signed","long","long"):("type",C_Basetype("signed long long")),

        ("struct",):("metatype",C_Metatype("struct")),
        ("union",):("metatype",C_Metatype("union")),
        ("enum",):("metatype",C_Metatype("enum"))
    })

    # ("type",C_Type)
    # ("metatype",C_Metatype)
    # ("var",C_Var)
    # ("const",C_Const)

    return symtable

def parseType(idx: Ref,tokens: list[Token],symTable: SymTable) -> tuple:
    '''return one of (C_Type ,var_name:str)'''
    typenames = []
    _,match,_,_ = tools(idx,tokens)

    while idx.val < len(tokens) and tokens[idx.val].tktype == "identifier":
        typename = tokens[idx.val].value ; typetuple = tuple((*typenames,typename))
        if (symItem := symTable.get(typetuple)) and symItem[0] in ["metatype","type"]:
            typenames.append(typename)
            idx.val += 1
        else:
            break

    if not typenames:
        return None,None # not a type
    
    var_name = None
    basetype = symTable.get(tuple(typenames))[1]
    if type(basetype) == C_Metatype:
        if tk := match("identifier"):
            var_name = tk.value
        return basetype , var_name

    def solve_type(basetype):
        '''return TopType & BottomType'''
        nonlocal var_name
        top_type = basetype ; bottom_type = None
        mid_top_type , mid_bottom_type = None , None
        while match("operator","*"):
            top_type = C_Pointer(top_type)
            if bottom_type is None:
                bottom_type = top_type
        if tk := match("identifier"):
            var_name = tk.value
        elif match("operator","("):
            mid_top_type , mid_bottom_type = solve_type(None)
            match("operator",")")
        if match("operator","("):
            argtypes = []
            while True:
                argtypes.append(parseType(idx,tokens,symTable))
                if match("operator",")"):
                    break
                else:
                    match("operator",",")
            top_type = C_Func(top_type,argtypes)
            if bottom_type is None:
                bottom_type = top_type
        else:
            dimensions = []
            while match("operator","["):
                arr_size = match("integer").value
                dimensions.append(arr_size)
                match("operator","]")
            if dimensions:
                top_type = C_Array(top_type,tuple(dimensions))
                if bottom_type is None:
                    bottom_type = top_type
        
        if mid_top_type and mid_bottom_type:
            if type(mid_bottom_type) == C_Func:
                mid_bottom_type.rettype = top_type
            elif type(mid_bottom_type) == C_Pointer:
                mid_bottom_type.oftype = top_type
            elif type(mid_bottom_type) == C_Array:
                mid_bottom_type.oftype = top_type
            return mid_top_type,bottom_type
        
        return top_type,bottom_type
    basetype,_ = solve_type(basetype)

    return basetype,var_name

def parseDeclaration(idx: Ref,tokens: list[Token],symTable: SymTable):
    var_type , var_name = parseType(idx,tokens,symTable)
    _,match,_,_ = tools(idx,tokens)

    if type(var_type) == C_Metatype:
        # metatypes
        newtype = None
        if var_type.typename   == "struct":
            if match("operator","{"):
                fields = []
                while True:
                    field_type, field_name = parseType(idx,tokens,symTable)
                    if field_type and field_name:
                        fields.append((field_type,field_name))
                    if match("operator","}"):
                        break
                    else:
                        match("operator",";")
                newtype = C_Struct(fields)
            else:
                newtype = C_Struct([])
        elif var_type.typename == "union":
            if match("operator","{"):
                fields = []
                while True:
                    field_type, field_name = parseType(idx,tokens,symTable)
                    if field_type and field_name:
                        fields.append((field_type,field_name))
                    if match("operator","}"):
                        break
                    else:
                        match("operator",";")
                newtype = C_Union(fields)
            else:
                newtype = C_Union([])
        elif var_type.typename == "enum":
            val = 0; newtype = C_Enum()
            if match("operator","{"):
                while True:
                    if tk := match("identifier"):
                        if match("operator","="):
                            if valtk := match("integer"):
                                val = valtk.value
                        symTable.set((tk.value,),("const",C_Const(newtype,val)))
                        val += 1
                    if match("operator","}"):
                        break
                    else:
                        match("operator",",")
        if var_name:
            symTable.set((var_type.typename,var_name),("type",newtype))
    
    # otherwise we are declaring a variable
    else:
        symTable.set((var_name,),("var",C_Var(var_type)))
    
    if match("operator","="):
        # with init
        ...
    elif match("operator","{"):
        # function
        ...


def program(idx: Ref,tokens: list[Token]) -> ASTNode:
    children = []
    this = ASTNode("program",children,())
    symtable = rootTable()

    return this