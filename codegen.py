import struct
from common import *
from parser import SymTable

opcode_text = '''
NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,
OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,
FADD,FSUB,FMUL,FDIV,I2F ,F2I ,JREG,JSRR,
OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCPY,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,SCNF
'''

opcode = {v.strip() : i for i,v in enumerate(opcode_text.split(','))}

class Image:
    def __init__(self):
        self.block = bytearray()
    
    def extend(self,bs):
        start = len(self.block)
        self.block.extend(bs)
        return start
    
    def __len__(self):
        return len(self.block)

class LiteralPool:
    def __init__(self,image: Image):
        self.image  = image
        self.mapper = {}
    
    def alloc(self,s : str):
        if s not in self.mapper:
            self.mapper[s] = self.image.extend(s.encode() + b'\0')
        return self.mapper[s]

class AllocBackend:
    def __init__(self,bktype : str,image = None):
        self.bktype = bktype # [image , stack]
        self.image  = image # neccessary for image 
        self.stkp   = 0

    def alloc(self,bs : bytes):
        if self.bktype == "image":
            self.image : Image
            return self.image.extend(bs)
        elif self.bktype == "stack":
            self.stkp -= len(bs)
            return self.stkp

    def allocspace(self,size: int):
        if self.bktype == "image":
            return self.image.extend(b'\0' * size)
        elif self.bktype == "stack":
            self.stkp -= size
            return self.stkp

    def align(self,size : int):
        if self.bktype == "image":
            if len(self.image) % size != 0:
                self.image.extend(b'\0' * (size - len(self.image) % size))
            return len(self.image)
        elif self.bktype == "stack":
            if self.stkp % size != 0:
                self.stkp -= self.stkp % size
            return self.stkp

    def end(self):
        if self.bktype == "image":
            return len(self.image)
        elif self.bktype == "stack":
            return self.stkp

class Allocator:
    def __init__(self,father : "Allocator" = None,backend : AllocBackend = None):
        self.father  = father
        self.backend = backend
        self.symmap  = {} # sym:(bktype,position)

    def allocspace(self,sym,size):
        start = self.backend.allocspace(size)
        self.symmap[sym] = (self.backend.bktype,start)

    def alloc(self,sym,bs):
        start = self.backend.alloc(bs)
        self.symmap[sym] = (self.backend.bktype,start)

    def get(self,sym):
        if sym in self.symmap:
            return self.symmap[sym]
        if self.father:
            return self.father.get(sym)
        return None

@dataclass
class CodegenContext:
    image       : Image
    literalpool : LiteralPool
    allocator   : Allocator
    symtable    : SymTable

def entry(astroot: ASTNode) -> bytes:
    image = Image()
    literalpool  = LiteralPool(image)
    allocbackend = AllocBackend("image",image)
    allocator    = Allocator(father=None,backend=allocbackend)
    symtable     = astroot.metas[0]

    ctx = CodegenContext(image,literalpool,allocator,symtable)

    program(ctx,astroot)
    disasm(ctx.image.block)

    return ctx.image.block

def disasm(image: bytearray):
    rev_opcode = {v: k for k, v in opcode.items()}
    
    print(f"{'Addr':<6} | {'Opcode':<8} | {'Value (Dec)':<24} | {'Hex':<24} | {'Raw Bytes'}")
    print("-" * 84)

    for idx in range(0, len(image), 8):
        bs = image[idx:idx+8]
        decimal = int.from_bytes(bs, 'little', signed=True)
        hex_val = f"0x{int.from_bytes(bs, 'little', signed=False):x}"
        
        op_name = rev_opcode.get(decimal, "")
        ascii_repr = "".join(chr(b) if 32 <= b <= 126 else "." for b in bs)

        if op_name:
            display_op = f"[{op_name}]"
        else:
            display_op = f"(data)"

        print(f"{idx:<6} | {display_op:<8} | {decimal:<24} | {hex_val:<24} | {ascii_repr}")

def program(ctx : CodegenContext,astnode : ASTNode):
    program_symtab_init(ctx,astnode) # alloc static space for variables
    poolinit(ctx,astnode)            # init strings to literal pool
    static_init(ctx,astnode)         # fill in init data for static vars
    codegen_functions(ctx,astnode)

    print('allocator.symmap  : ',ctx.allocator.symmap)
    print('literalpool.mapper: ',ctx.literalpool.mapper)

def codegen_functions(ctx: CodegenContext, astroot : ASTNode):
    for astnode in astroot.children:
        if astnode.nodeType != "function":
            continue
        codegen_function(ctx,astnode)

def codegen_function(ctx : CodegenContext, astnode : ASTNode):
    # navigate entry point JMP to this function
    function_name , func_type, func_symtable = astnode.metas # missed 1 symtable here?!

    # align .text with 8 bytes
    ctx.allocator.backend.align(8) # at this point , allocator is still an image allocator

    ent_pos = ctx.image.extend(
        i64(opcode["ENT"]) + i64(0)
    )
    var_at, var_pos = ctx.allocator.get(function_name) # var_at could only be "image" here
    ctx.image.block[var_pos + 8:var_pos + 16] = i64(ent_pos)

    # fill in _main if function is main
    if function_name == "main":
        ctx.image.block[8:16] = i64(ent_pos)

    # function scope start
    new_allocator = Allocator(ctx.allocator,AllocBackend("stack"))
    
    func_type : C_Func
    func_symtable : SymTable

    arg_count = len(func_type.argtype)
    for idx , (arg_type, arg_name) in enumerate(func_type.argtype):
        # all arguments are resized to 8 when passed as a parameter!
        new_allocator.symmap[arg_name] = ("stack",8 * (arg_count - 1 - idx) + 16)

    ctx = CodegenContext(
        ctx.image,ctx.literalpool,new_allocator,func_symtable
    )
    codegen_actions(ctx,astnode.children[0])

    # fill in ENT for stack allocation
    ctx.allocator.backend.align(8)
    ctx.image.block[ent_pos + 8:ent_pos + 16] = i64(ctx.allocator.backend.end() // 8)
    ctx.image.extend(i64(opcode["LEV"])) # auto return for lazy guys 

def codegen_actions(ctx : CodegenContext, astnode : ASTNode):
    symtable : SymTable = astnode.metas[0]
    new_allocator       = Allocator(ctx.allocator,ctx.allocator.backend)
    ctx = CodegenContext(
        ctx.image,ctx.literalpool,new_allocator,symtable
    )
    
    # build symbol table for scope
    symdict = symtable.mapper
    for var_name_tuple , (var_type,typeinfo) in symdict.items():
        if var_type != 'var':
            continue
        typeinfo : C_Var
        var_type = typeinfo.oftype
        var_name = var_name_tuple[0]
        new_allocator.allocspace(var_name,type_size(var_type))    

    # compile actions here !!!! WIP
    for action_ast in astnode.children:
        codegen_action(ctx,action_ast)

builtin_funcs = {
    'open':'OPEN', 'read': 'READ', 'close': 'CLOSE',
    'printf':'PRTF',  'malloc':'MALC', 'free':'FREE',
    'memset':'MSET',  'memcpy':'MCPY', 'memcmp':'MCMP',
    'exit': 'EXIT',   'strcmp':'SCMP', 'strlen':'SLEN',
    'strstr': 'SSTR', 'strcat':'SCAT', 'scanf': 'SCNF'
}

def codegen_builtin_funcs(ctx : CodegenContext, astnode: ASTNode):
    func_ast  : ASTNode = astnode.children[0]
    args_cnt  = len(astnode.children) - 1
    func_name = func_ast.metas[0]
    
    opcode_name = builtin_funcs[func_name]
    ctx.image.extend(
        i64(opcode[opcode_name]) \
        + i64(opcode['ADJ']) \
        + i64(args_cnt)
    )

def ast_type(ctx: CodegenContext,astnode : ASTNode):
    '''None for unknown'''

    if astnode.nodeType == "call":
        func_ast : ASTNode = astnode.children[0]
        if func_ast.nodeType == "var":
            func_name = func_ast.metas[0]
            _ , func_type = ctx.symtable.get((func_name,))
            func_type : C_Func
            ret_type = func_type.rettype
            return ret_type
        else:
            return None
        
    # other evaluations

def codegen_action(ctx : CodegenContext,astnode : ASTNode):
    if astnode.nodeType == "call":
        func_ast  : ASTNode = astnode.children[0]
        args_asts : ASTNode = astnode.children[1:]

        for arg_ast in args_asts:
            codegen_action(ctx,arg_ast)
            ctx.image.extend(i64(opcode["PSH"]))

        if func_ast.nodeType == "var": # calling with function name
            func_name = func_ast.metas[0]
            if func_name in builtin_funcs:
                codegen_builtin_funcs(ctx,astnode)    
            else:
                bktype , func_pos = ctx.allocator.get(func_name)
                if bktype == "stack":
                    ctx.image.extend(i64(opcode["LEA"]) + i64(func_pos))
                    ctx.image.extend(i64(opcode["LI"])  + i64(opcode["JSRR"]))
                    ctx.image.extend(i64(opcode["ADJ"]) + i64(len(args_asts)))
                elif bktype == "image":
                    ctx.image.extend(i64(opcode["JSR"]) + i64(func_pos))
                    ctx.image.extend(i64(opcode["ADJ"]) + i64(len(args_asts)))
        else:
            # otherwise call with evaluated address
            codegen_action(ctx,func_ast)
            ctx.image.extend(i64(opcode["JSRR"]))
            ctx.image.extend(i64(opcode["ADJ"]) + i64(len(args_asts)))

    elif astnode.nodeType == "string":
        literal = astnode.metas[0]
        image_pos = ctx.literalpool.alloc(literal)
        ctx.image.extend(i64(opcode["IMM"]) + i64(image_pos))

def i8(x : int) -> bytes:

    return x.to_bytes(1,'little',signed=True)

def i64(x : int) -> bytes:
    return x.to_bytes(8,'little',signed=True)

def u8(x : int) -> bytes:
    return x.to_bytes(1,'little',signed=False)

def u64(x : int) -> bytes:
    return x.to_bytes(8,'little',signed=False)

def f64(x : float) -> bytes:
    return struct.pack('<d',x)

def program_symtab_init(ctx : CodegenContext,astnode : ASTNode):
    # add _main entry point at very beginning
    ctx.allocator.alloc("_main",i64(opcode["JMP"]) + i64(0))

    symtable : SymTable = astnode.metas[0]
    symdict  : dict     = symtable.mapper

    for var_name_tuple, (var_type,typeinfo) in symdict.items():
        if var_type != 'var':
            continue
        var_name = var_name_tuple[0]
        typeinfo : C_Var
        vartype = typeinfo.oftype
        allocvar(ctx,var_name,vartype)

def type_size(var_type) -> int:
    if type(var_type) == C_Struct:
        totalsize = 0
        for childtype,_ in var_type.fields:
            totalsize += type_size(childtype)
        return totalsize
    if type(var_type) == C_Array:
        element_type = var_type.oftype
        element_size = type_size(element_type)
        total_element_count = 1
        for d in var_type.dimension:
            total_element_count *= d
        return element_size * total_element_count
    if type(var_type) == C_Enum:
        return 8
    if type(var_type) == C_Const:
        return 0
    if type(var_type) == C_Pointer:
        return 8
    if type(var_type) == C_Func:
        return 16
    if type(var_type) == C_Union:
        maxsize = 0
        for field_type, _ in var_type.fields:
            maxsize = max(maxsize,type_size(field_type))
        return maxsize
    if type(var_type) == C_Enum:
        return 8
    if type(var_type) == C_Basetype:
        if var_type.typename == "char" or var_type == "unsigned char":
            return 1
        return 8
    assert False # unreachable

def struct_offset(struct_type : C_Struct,field_name : str):
    offset = 0
    for field_type, struct_field_name in struct_type.fields:
        if struct_field_name == field_name:
            return offset , field_type
        offset += type_size(field_type)
    return offset

def struct_idx_offset(struct_type : C_Struct,idx : int):
    offset = 0
    for i , (field_type, _) in enumerate(struct_type.fields):
        if i == idx:
            return offset , field_type
        offset += type_size(field_type)
    return offset , None

def array_offset(array_type : C_Array,idxarr : tuple[int]):
    element_size : int = type_size(array_type.oftype)
    realidx = 0
    for dlen, didx in zip(array_type.dimension,idxarr):
        realidx += dlen * didx
    return realidx * element_size

def allocvar(ctx : CodegenContext, sym : str, vartype : Any):
    if type(vartype) == C_Func:
        ctx.allocator.backend.align(8) # align before function !!!
        ctx.allocator.alloc(sym,i64(opcode["JMP"]) + i64(0))
        return
    ctx.allocator.allocspace(sym,type_size(vartype))

def poolinit(ctx : CodegenContext ,astnode : ASTNode):

    def traverse(node : ASTNode):
        if node.nodeType == "string":
            ctx.literalpool.alloc(node.metas[0])
        for child in node.children:
            traverse(child)

    traverse(astnode)

def static_init(ctx : CodegenContext, astroot : ASTNode):

    def assign_element(var_type,literal_ast,var_pos):
        if literal_ast.nodeType == "string":
            if type(var_type) == C_Pointer:
                target_addr = ctx.literalpool.alloc(literal_ast.metas[0]) 
                ctx.image.block[var_pos:var_pos + 8] = i64(target_addr)
            elif type(var_type) == C_Array:
                string_literal = literal_ast.metas[0]
                for i,c in enumerate(string_literal):
                    ctx.image.block[var_pos + i] = ord(c)
        elif literal_ast.nodeType == "integer":
            int_literal = literal_ast.metas[0]
            if type_size(var_type) == 1:
                ctx.image.block[var_pos] = int_literal
            else:
                ctx.image.block[var_pos:var_pos + 8] = i64(int_literal)
        elif literal_ast.nodeType == "var":
            const_name = literal_ast.metas[0] 
            const_val  = symtable.get((const_name,))[1].value
            if type_size(var_type) == 1:
                ctx.image.block[var_pos] = const_val
            else:
                ctx.image.block[var_pos:var_pos + 8] = i64(const_val)
        elif literal_ast.nodeType == "float":
            float_literal = literal_ast.metas[0]
            ctx.image.block[var_pos:var_pos+8] = f64(float_literal)

    for child in astroot.children:
        child : ASTNode
        
        if child.nodeType == "actions":
            static_init(ctx,child) 

        elif child.nodeType == "assign":
            var_ast     : ASTNode = child.children[0]
            literal_ast : ASTNode = child.children[1]

            var_name    = var_ast.metas[0]
            symtable : SymTable   = ctx.symtable

            _ , var_type = symtable.get((var_name,))
            var_type = var_type.oftype
            _ , var_pos  = ctx.allocator.get(var_name)

            assign_element(var_type,literal_ast,var_pos)

        elif child.nodeType == "init_assign":
            var_name     : ASTNode = child.children[0].metas[0]
            initlist     : ASTNode = child.children[1].metas[0]

            _ , var_type = ctx.symtable.get((var_name,))
            var_type = var_type.oftype
            _ , var_pos  = ctx.allocator.get(var_name)

            def init_assign(var_type : Any,content: list[tuple],var_pos: int):
                if type(var_type) == C_Array:
                    if len(var_type.dimension) > 1:
                        childtype = C_Array(var_type.oftype,var_type.dimension[1:])
                    else:
                        childtype = var_type.oftype
                    childsize = type_size(childtype)
                    for idx, lstast in content:
                        if lstast.nodeType == "initlist":
                            contentlst = lstast.metas[0]
                            init_assign(childtype,contentlst,var_pos + childsize * idx)
                        else:
                            elemast    = lstast
                            init_assign(childtype,elemast,var_pos + childsize * idx)
                elif type(var_type) == C_Struct:
                    for idx,elemast in content:
                        if type(idx) == str:
                            field_offset , field_type = struct_offset(var_type,idx)
                        elif type(idx) == int:
                            field_offset , field_type = struct_idx_offset(var_type,idx)
                        elemast : ASTNode
                        if elemast.nodeType == "initlist":
                            contentlst = elemast.metas[0]
                            init_assign(field_type,contentlst,var_pos + field_offset)
                        else:
                            init_assign(field_type,elemast,var_pos + field_offset)
                else:
                    assign_element(var_type,content,var_pos)

            init_assign(var_type,initlist,var_pos)