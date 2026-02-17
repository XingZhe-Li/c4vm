from common import *

class Ref:
    def __init__(self,val):
        self.val = val
    def __repr__(self):
        return "Ref({0})".format(self.val)

REPR_SYMTABLE = False

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
    def __repr__(self):
        if REPR_SYMTABLE:
            return "SymTable(mapper={0},father={1})".format(self.mapper,self.father)
        return "..."

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
        if tk is None:return None
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
        ("enum",):("metatype",C_Metatype("enum")),

        ("typedef",):("typedef",C_Typedef(None))
    })

    # ("type",C_Type)
    # ("metatype",C_Metatype)
    # ("var",C_Var)
    # ("const",C_Const)

    return symtable

def parseBasetype(idx: Ref,tokens: list[Token] , symTable : SymTable):
    typenames = []
    while idx.val < len(tokens) and tokens[idx.val].tktype == "identifier":
        typename = tokens[idx.val].value ; typetuple = tuple((*typenames,typename))
        if (symItem := symTable.get(typetuple)) and symItem[0] in ["typedef","metatype","type"]:
            typenames.append(typename)
            idx.val += 1
        else:
            break
    if not typenames:
        return None
    return symTable.get(tuple(typenames))[1]

def parseType(idx: Ref,tokens: list[Token],symTable: SymTable,basetype = None) -> tuple:
    '''return one of (C_Type ,var_name:str)'''
    _,match,_,_ = tools(idx,tokens)

    if basetype is None:
        basetype = parseBasetype(idx,tokens,symTable)
        if basetype is None:
            return None,None

    var_name = None
    if type(basetype) == C_Typedef:
        newtype,typename = parseType(idx,tokens,symTable)
        return C_Typedef(newtype) , typename

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

def declaration(idx: Ref,tokens: list[Token],symTable: SymTable) -> ASTNode:
    '''it's possible to return a ASTNode if here is some initialization'''
    basetype = parseBasetype(idx,tokens,symTable)
    _,match,_,_ = tools(idx,tokens)

    if type(basetype) == C_Typedef:
        newtype , typename = parseType(idx,tokens,symTable,basetype)
        if typename:
            symTable.set((typename,),("type",newtype.of))

    elif type(basetype) == C_Metatype:
        # metatypes
        var_type , var_name = parseType(idx,tokens,symTable,basetype)
        newtype = None
        if var_type.typename   == "struct":
            if match("operator","{"):
                fields = []
                while True:
                    basetype = parseBasetype(idx,tokens,symTable)
                    while True:
                        field_name , field_type = parseType(idx,tokens,symTable,basetype)
                        if field_type and field_name:
                            fields.append((field_type,field_name))
                        if not match("operator",","):
                            break
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
        rootnode = ASTNode("actions",[],())
        while True:
            var_type , var_name = parseType(idx,tokens,symTable,basetype)
            symTable.set((var_name,),("var",C_Var(var_type)))
        
            if match("operator","="):
                # with init
                if match("operator","{"):
                    astnode = initlist(idx,tokens,symTable)
                    match("operator","}")
                    astnode = ASTNode("init_assign",[
                        ASTNode("var",[],(var_name,)),
                        astnode
                    ],())
                    rootnode.children.append(astnode)
                else:
                    astnode = ASTNode("assign",[
                        ASTNode("var",[],(var_name,)),
                        expression(idx,tokens,symTable,14)
                    ],())
                    rootnode.children.append(astnode)
            elif match("operator","{"):
                astnode = ASTNode("function",[statements(idx,tokens,symTable)],(var_name,var_type,))
                match("operator","}")
                rootnode.children.append(astnode)
            if not match("operator",","):
                break
        
        if len(rootnode.children) == 0:
            return None
        elif len(rootnode.children) == 1:
            return rootnode.children[0]
        else:
            return rootnode

def initlist(idx:Ref, tokens: list[Token], symTable: SymTable) -> ASTNode:
    peek,match,_,_ = tools(idx,tokens) ; autoidx = 0
    lst = [] ; folds = 0 # [(key,value)]
    while True:
        if match("operator","["):
            autoidx = match("integer").value
            match("operator","]")
            match("operator","=")
            value = expression(idx,tokens,symTable,14)
            lst.append((autoidx,value))
            autoidx += 1
        elif match("operator","."):
            tk = match("identifier")
            match("operator","=")
            value = expression(idx,tokens,symTable,14)
            lst.append((tk.value,value))
        elif match("operator","{"):
            folds += 1
        else:
            if peek() is None or peek().tktype == "operator" and peek().value == "}":
                if folds > 0:
                    folds -= 1
                    match("operator","}")
                else:
                    break
            value = expression(idx,tokens,symTable,14)
            lst.append((autoidx,value))
            autoidx += 1
        match("operator",",")
    return ASTNode("initlist",[],(lst,))

def expression(idx: Ref, tokens: list[Token],symTable: SymTable,prec=15) -> ASTNode:
    _,match,_,_ = tools(idx,tokens)
    lhs = None

    if prec >= 15:
        lhs = expression(idx,tokens,symTable,14)
        while True:
            if match("operator",","):
                lhs = ASTNode("comma",[lhs,expression(idx,tokens,symTable,14)],())
            else:
                break
        return lhs

    if prec >= 14:
        lhs = expression(idx,tokens,symTable,13)
        while True:
            if match("operator","="):
                lhs = ASTNode("assign",[lhs,expression(idx,tokens,symTable,13)],())
            elif match("operator","/="):
                lhs = ASTNode("assign",[lhs,ASTNode("div",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","*="):
                lhs = ASTNode("assign",[lhs,ASTNode("mul",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","%="):
                lhs = ASTNode("assign",[lhs,ASTNode("mod",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","+="):
                lhs = ASTNode("assign",[lhs,ASTNode("add",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","-="):
                lhs = ASTNode("assign",[lhs,ASTNode("sub",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","<<="):
                lhs = ASTNode("assign",[lhs,ASTNode("shl",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator",">>="):
                lhs = ASTNode("assign",[lhs,ASTNode("shr",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","&="):
                lhs = ASTNode("assign",[lhs,ASTNode("bitand",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","^="):
                lhs = ASTNode("assign",[lhs,ASTNode("bitxor",[lhs,expression(idx,tokens,symTable,13)],())],())
            elif match("operator","|="):
                lhs = ASTNode("assign",[lhs,ASTNode("bitor",[lhs,expression(idx,tokens,symTable,13)],())],())
            else:
                break
        return lhs

    if prec >= 13:
        lhs = expression(idx,tokens,symTable,12)
        while True:
            if match("operator","?"):
                true_ret  = expression(idx,tokens,symTable,12)
                match("operator",":")
                false_ret = expression(idx,tokens,symTable,12)
                lhs = ASTNode("cond",[lhs,true_ret,false_ret],())
            else:
                break
        return lhs

    if prec >= 12:
        lhs = expression(idx,tokens,symTable,11)
        while True:
            if match("operator","||"):
                lhs = ASTNode("or",[lhs,expression(idx,tokens,symTable,11)],())
            else:
                break
        return lhs

    if prec >= 11:
        lhs = expression(idx,tokens,symTable,10)
        while True:
            if match("operator","&&"):
                lhs = ASTNode("and",[lhs,expression(idx,tokens,symTable,10)],())
            else:
                break
        return lhs

    if prec >= 10:
        lhs = expression(idx,tokens,symTable,9)
        while True:
            if match("operator","|"):
                lhs = ASTNode("bitor",[lhs,expression(idx,tokens,symTable,9)],())
            else:
                break
        return lhs

    if prec >= 9:
        lhs = expression(idx,tokens,symTable,8)
        while True:
            if match("operator","^"):
                lhs = ASTNode("bitxor",[lhs,expression(idx,tokens,symTable,8)],())
            else:
                break
        return lhs

    if prec >= 8:
        lhs = expression(idx,tokens,symTable,7)
        while True:
            if match("operator","&"):
                lhs = ASTNode("bitand",[lhs,expression(idx,tokens,symTable,7)],())
            else:
                break
        return lhs

    if prec >= 7:
        lhs = expression(idx,tokens,symTable,6)
        while True:
            if match("operator","=="):
                lhs = ASTNode("eq",[lhs,expression(idx,tokens,symTable,6)],())
            elif match("operator","!="):
                lhs = ASTNode("ne",[lhs,expression(idx,tokens,symTable,6)],())
            else:
                break
        return lhs

    if prec >= 6:
        lhs = expression(idx,tokens,symTable,5)
        while True:
            if match("operator",">"):
                lhs = ASTNode("gt",[lhs,expression(idx,tokens,symTable,5)],())
            elif match("operator",">="):
                lhs = ASTNode("ge",[lhs,expression(idx,tokens,symTable,5)],())
            elif match("operator","<"):
                lhs = ASTNode("lt",[lhs,expression(idx,tokens,symTable,5)],())
            elif match("operator","<="):
                lhs = ASTNode("le",[lhs,expression(idx,tokens,symTable,5)],())
            else:
                break
        return lhs

    if prec >= 5:
        lhs = expression(idx,tokens,symTable,4)
        while True:
            if match("operator","<<"):
                lhs = ASTNode("shl",[lhs,expression(idx,tokens,symTable,4)],())
            elif match("operator","-"):
                lhs = ASTNode("shr",[lhs,expression(idx,tokens,symTable,4)],())
            else:
                break
        return lhs

    if prec >= 4:
        lhs = expression(idx,tokens,symTable,3)
        while True:
            if match("operator","+"):
                lhs = ASTNode("add",[lhs,expression(idx,tokens,symTable,3)],())
            elif match("operator","-"):
                lhs = ASTNode("sub",[lhs,expression(idx,tokens,symTable,3)],())
            else:
                break
        return lhs

    if prec >= 3:
        lhs = expression(idx,tokens,symTable,2)
        while True:
            if match("operator","/"):
                lhs = ASTNode("div",[lhs,expression(idx,tokens,symTable,2)],())
            elif match("operator","*"):
                lhs = ASTNode("mul",[lhs,expression(idx,tokens,symTable,2)],())
            elif match("operator","%"):
                lhs = ASTNode("mod",[lhs,expression(idx,tokens,symTable,2)],())
            else:
                break
        return lhs

    if prec >= 2:
        if match("operator","++"):
            lhs = ASTNode("incret",[expression(idx,tokens,symTable,2)],())
        elif match("operator","--"):
            lhs = ASTNode("decret",[expression(idx,tokens,symTable,2)],())
        elif match("operator","*"):
            lhs = ASTNode("deaddr",[expression(idx,tokens,symTable,2)],())
        elif match("operator","&"):
            lhs = ASTNode("addr",[expression(idx,tokens,symTable,2)],())
        elif match("operator","!"):
            lhs = ASTNode("not",[expression(idx,tokens,symTable,2)],())
        elif match("identifier","sizeof"):
            lhs = ASTNode("sizeof",[expression(idx,tokens,symTable,2)],())
        elif match("operator","~"):
            lhs = ASTNode("bitnot",[expression(idx,tokens,symTable,2)],())
        elif match("operator","+"):
            lhs = expression(idx,tokens,symTable,2)
        elif match("operator","-"):
            lhs = ASTNode("neg",[expression(idx,tokens,symTable,2)],())
        else:
            snapshot = idx.val
            if match("operator","("):
                conv_type , _ = parseType(idx,tokens,symTable)
                if conv_type:
                    lhs = ASTNode("as",[expression(idx,tokens,symTable,2)],(conv_type,))
                    match("operator",")")
                else:
                    idx.val = snapshot
                    lhs = expression(idx,tokens,symTable,1)
            else:
                lhs = expression(idx,tokens,symTable,1)

            while True:
                if match("operator","++"):
                    lhs = ASTNode("retinc",[lhs],())
                elif match("operator","--"):
                    lhs = ASTNode("retdec",[lhs],())
                else:
                    break
        return lhs        

    if prec >= 1:
        tk : Token
        if match("operator","("):
            lhs = expression(idx,tokens,symTable)
            match("operator",")")
        elif tk := match("identifier"):
            var_name = tk.value
            lhs = ASTNode("var",[],(var_name,))
        elif tk := match("integer"):
            lhs = ASTNode("integer",[],(tk.value,))
        elif tk := match("string"):
            lhs = ASTNode("string",[],(tk.value,))
        elif tk := match("float"):
            lhs = ASTNode("float",[],(tk.value,))

        while True:
            if match("operator","("):
                args = []
                while True:
                    args.append(expression(idx,tokens,symTable,14))
                    if not match("operator",","):
                        break
                match("operator",")")
                lhs = ASTNode("call",[lhs,*args],())
            elif match("operator","["):
                lhs = ASTNode("index",[lhs,expression(idx,tokens,symTable)],())
                match("operator","]")
            elif match("operator","."):
                tk = match("identifier")
                lhs = ASTNode("attr",[lhs],(tk.value,))
            elif match("operator","->"):
                tk = match("identifier")
                lhs = ASTNode("ptr_attr",[lhs],(tk.value,))
            else:
                break
        return lhs

def statements(idx: Ref,tokens: list[Token],symTable : SymTable) -> ASTNode:
    _,match,_,_ = tools(idx,tokens)
    symTable = symTable.derive()
    children = []
    rootnode = ASTNode("actions",children,(symTable,))

    while True:
        stmt = statement(idx,tokens,symTable)
        if stmt:
            children.append(stmt)
        if match("operator","}"):
            break
    
    return rootnode

def statement(idx: Ref,tokens: list[Token],symTable : SymTable) -> ASTNode:
    peek,match,_,_ = tools(idx,tokens)

    if match("operator",";"):
        return None
    if not peek() or peek().tktype == "operator" and peek().value == "}":
        return None
    
    if match("operator","{"):
        astnode = statements(idx,tokens,symTable)
        match("operator","}")
        return astnode
    elif match("identifier","if"):
        match("operator","(")
        cond = expression(idx,tokens,symTable,14)
        match("operator",")")
        iftrue = statement(idx,tokens,symTable)
        iffalse = None
        if match("identifier","else"):
            iffalse = statement(idx,tokens,symTable)
        if iffalse:
            return ASTNode("ifelse",[cond,iftrue,iffalse],())
        return ASTNode("if",[cond,iftrue],())
    elif match("identifier","while"):
        match("operator","(")
        cond = expression(idx,tokens,symTable,14)
        match("operator",")")
        loop = statement(idx,tokens,symTable)
        return ASTNode("while",[cond,loop],())
    elif match("identifier","for"):
        match("operator","(")
        init_clause = declaration(idx,tokens,symTable)
        match("operator",";")
        cond_clause = expression(idx,tokens,symTable,14)
        match("operator",";")
        op_clause = expression(idx,tokens,symTable,14)
        match("operator",")")
        loop = statement(idx,tokens,symTable)
        return ASTNode("for",[init_clause,cond_clause,op_clause,loop],())
    elif match("identifier","do"):
        loop = statement(idx,tokens,symTable)
        match("identifier","while")
        match("identifier","(")
        cond = expression(idx,tokens,symTable,14)
        match("identifier",")")
        match("identifier",";")
        return ASTNode("do_while",[cond,loop],())
    elif match("identifier","return"):
        retval = expression(idx,tokens,symTable,14)
        match("operator",";")
        return ASTNode("ret",[retval],())
    else:
        snapshot = idx.val
        if parseBasetype(idx,tokens,symTable):
            idx.val = snapshot
            astnode = declaration(idx,tokens,symTable)
            match("operator",";")
            return astnode
        else:
            idx.val = snapshot
            expr = expression(idx,tokens,symTable)
            match("operator",";")
            return expr

def program(idx: Ref,tokens: list[Token]) -> ASTNode:
    children = []
    symtable = rootTable()
    this = ASTNode("program",children,(symtable,))

    while idx.val < len(tokens):
        dec = declaration(idx,tokens,symtable)
        if dec:
            children.append(dec)
        if idx.val < len(tokens) and tokens[idx.val].tktype == "operator" and tokens[idx.val].value == ";":
            idx.val += 1

    return this