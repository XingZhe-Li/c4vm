"""将 AST 降为 c4vm 字节码，处理镜像布局、变量存储、类型大小和跳转回填。

镜像以字节为地址单位，指令及立即数各占 8 字节。布局依次为启动跳转、
全局存储/函数跳转桩、字符串池和函数体；局部变量使用相对 BP 的负字节偏移。
操作码编号和调用约定必须与唯一解释器 c4vm.c 一致。
"""

import struct
from common import *
from parser import SymTable

opcode_text = '''
NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,
OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,
FADD,FSUB,FMUL,FDIV,I2F ,F2I ,JREG,JSRR,NOT ,WRIT,GETC,
OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCPY,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,SCNF
'''

opcode = {v.strip() : i for i,v in enumerate(opcode_text.split(','))}

class Image:
    """可追加并原位回填的原始镜像；extend 返回写入位置的字节地址。"""
    def __init__(self):
        self.block = bytearray()
    
    def extend(self,bs):
        start = len(self.block)
        self.block.extend(bs)
        return start
    
    def __len__(self):
        return len(self.block)

class LiteralPool:
    """按字符串内容去重，为 UTF-8 字节串及结尾 NUL 分配镜像地址。"""
    def __init__(self,image: Image):
        self.image  = image
        self.mapper = {}
    
    def alloc(self,s : str):
        if s not in self.mapper:
            self.mapper[s] = self.image.extend(s.encode() + b'\0')
        return self.mapper[s]

class AllocBackend:
    """分配镜像中的正向存储，或函数帧中向负偏移增长的局部存储。"""
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
    """将词法作用域中的名称映射到存储位置；子块共享同一函数帧后端。"""
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
class FlowContext:
    """记录当前循环尚待回填的 break/continue 跳转地址。"""
    break_pos_lst     : list[int]
    continue_pos_lst  : list[int]

@dataclass
class CodegenContext:
    image       : Image
    literalpool : LiteralPool
    allocator   : Allocator
    symtable    : SymTable
    flowCtx     : FlowContext

def entry(astroot: ASTNode, verbose=False) -> bytes:
    """生成无文件头的原始镜像；verbose 仅控制调试字转储。"""
    image = Image()
    literalpool  = LiteralPool(image)
    allocbackend = AllocBackend("image",image)
    allocator    = Allocator(father=None,backend=allocbackend)
    symtable     = astroot.metas[0]

    ctx = CodegenContext(image,literalpool,allocator,symtable,None)

    program(ctx,astroot)
    if verbose:
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
    if not any(node.nodeType == "function" and node.metas[0] == "main" for node in astnode.children):
        raise ValueError("program must define main()")
    program_symtab_init(ctx,astnode) # alloc static space for variables
    poolinit(ctx,astnode)            # init strings to literal pool
    static_init(ctx,astnode)         # fill in init data for static vars
    codegen_functions(ctx,astnode)


def codegen_functions(ctx: CodegenContext, astroot : ASTNode):
    for astnode in astroot.children:
        if astnode.nodeType != "function":
            continue
        codegen_function(ctx,astnode)

def codegen_function(ctx : CodegenContext, astnode : ASTNode):
    # navigate entry point JMP to this function
    function_name , func_type, func_symtable = astnode.metas

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
        # BP+0 保存旧 BP，BP+8 保存返回地址；实参按声明顺序压栈，每槽 8 字节。
        new_allocator.symmap[arg_name] = ("stack",8 * (arg_count - 1 - idx) + 16)

    ctx = CodegenContext(
        ctx.image,ctx.literalpool,new_allocator,func_symtable,ctx.flowCtx
    )
    codegen_actions(ctx,astnode.children[0])

    # fill in ENT for stack allocation
    ctx.allocator.backend.align(8)
    ctx.image.block[ent_pos + 8:ent_pos + 16] = i64(-ctx.allocator.backend.end() // 8)
    if function_name == "main":
        ctx.image.extend(i64(opcode["IMM"]) + i64(0))
    ctx.image.extend(i64(opcode["LEV"])) # 函数走到末尾时仍需恢复调用者的栈帧。

def codegen_actions(ctx : CodegenContext, astnode : ASTNode):
    symtable : SymTable = astnode.metas[0]
    new_allocator       = Allocator(ctx.allocator,ctx.allocator.backend)
    ctx = CodegenContext(
        ctx.image,ctx.literalpool,new_allocator,symtable,ctx.flowCtx
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

    # 所有块级变量已分配位置，接着按源码顺序生成初始化及其他语句。
    for action_ast in astnode.children:
        codegen_action(ctx,action_ast)

builtin_funcs = {
    'open':'OPEN', 'read': 'READ', 'close': 'CLOS',
    'printf':'PRTF',  'malloc':'MALC', 'free':'FREE',
    'memset':'MSET',  'memcpy':'MCPY', 'memcmp':'MCMP',
    'exit': 'EXIT',   'strcmp':'SCMP', 'strlen':'SLEN',
    'strstr': 'SSTR', 'strcat':'SCAT', 'scanf': 'SCNF',
    'write': 'WRIT',  'getchar': 'GETC'
}

builtin_arity = {
    'open': (2, 3), 'read': (3, 3), 'close': (1, 1), 'printf': (1, 6),
    'malloc': (1, 1), 'free': (1, 1), 'memset': (3, 3), 'memcpy': (3, 3),
    'memcmp': (3, 3), 'exit': (1, 1), 'strcmp': (2, 2), 'strlen': (1, 1),
    'strstr': (2, 2), 'strcat': (2, 2), 'scanf': (1, 6), 'write': (3, 3), 'getchar': (0, 0),
}

def codegen_builtin_funcs(ctx : CodegenContext, astnode: ASTNode):
    func_ast  : ASTNode = astnode.children[0]
    args_cnt  = len(astnode.children) - 1
    func_name = func_ast.metas[0]
    minimum, maximum = builtin_arity[func_name]
    if not minimum <= args_cnt <= maximum:
        raise ValueError(f"{func_name} expects {minimum}..{maximum} arguments, got {args_cnt}")
    
    opcode_name = builtin_funcs[func_name]
    ctx.image.extend(
        i64(opcode[opcode_name]) \
        + i64(opcode['ADJ']) \
        + i64(args_cnt)
    )

def unpack_C_Var(x: C_Var):
    if type(x) == C_Var:
        return x.oftype
    return x

def normalize_bool(ctx):
    ctx.image.extend(i64(opcode["PSH"]) + i64(opcode["IMM"]) + i64(0) + i64(opcode["NE"]))

def is_byte(var_type):
    return type(var_type) == C_Basetype and var_type.typename in ["char", "signed char", "unsigned char"]

def is_floating(var_type):
    return type(var_type) == C_Basetype and var_type.typename in ["float", "double"]

def decay(var_type):
    if type(var_type) == C_Array:
        child = var_type.oftype if len(var_type.dimension) == 1 else C_Array(var_type.oftype, var_type.dimension[1:])
        return C_Pointer(child)
    return var_type

def normalize_byte(ctx, var_type):
    ctx.image.extend(i64(opcode["PSH"]) + i64(opcode["IMM"]) + i64(255) + i64(opcode["AND"]))
    if var_type.typename != "unsigned char":
        ctx.image.extend(i64(opcode["PSH"]) + i64(opcode["IMM"]) + i64(56) + i64(opcode["SHL"]))
        ctx.image.extend(i64(opcode["PSH"]) + i64(opcode["IMM"]) + i64(56) + i64(opcode["SHR"]))

def load_value(ctx, var_type):
    if is_byte(var_type):
        ctx.image.extend(i64(opcode["LC"]))
        if var_type.typename == "unsigned char":
            normalize_byte(ctx, var_type)
    elif type(var_type) not in [C_Array, C_Func]:
        ctx.image.extend(i64(opcode["LI"]))

def ast_type(ctx: CodegenContext,astnode : ASTNode):
    """推断表达式的值类型；变量保留 C_Var 包装，未知类型返回 None。"""

    if astnode.nodeType == "cached_value":
        return astnode.metas[0]
    if astnode.nodeType == "call":
        func_ast : ASTNode = astnode.children[0]
        if func_ast.nodeType == "var":
            func_name = func_ast.metas[0]
            
            symtuple = ctx.symtable.get((func_name,))
            if symtuple is None: 
                # for built-in functions
                return C_Basetype("long long") # conventionally , built-in functions return long long
            else:
                _ , func_type = symtuple
                func_type = unpack_C_Var(func_type)
                if type(func_type) == C_Pointer:
                    func_type = func_type.oftype
                if type(func_type) != C_Func:
                    raise ValueError(f"{func_name} is not a function")
                ret_type = func_type.rettype
                return ret_type
        else:
            return None
    elif astnode.nodeType == "var":
        var_name = astnode.metas[0]
        symbol = ctx.symtable.get((var_name,))
        if symbol is None:
            raise ValueError(f"undefined identifier: {var_name}")
        var_type_type , var_type = symbol
        return var_type
    # basic types
    elif astnode.nodeType == "integer":
        return C_Basetype("long long")
    elif astnode.nodeType == "float":
        return C_Basetype("double")
    elif astnode.nodeType == "string":
        return C_Array(C_Basetype("char"),(len(astnode.metas[0].encode("utf-8")) + 1,))
    elif astnode.nodeType in ["incret","decret","retinc","retdec","neg"]:
        return ast_type(ctx,astnode.children[0])
    elif astnode.nodeType in ["mod","shl","shr","bitand","bitor",
                              "bitxor","bitnot","and","or","not","eq","ne","lt","gt","le","ge"]:
        return C_Basetype("long long")
    elif astnode.nodeType in ["add","sub","mul","div"]:
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        ltype = decay(unpack_C_Var(ast_type(ctx,lhs)))
        rtype = decay(unpack_C_Var(ast_type(ctx,rhs)))

        if type(ltype) == C_Basetype and ltype.typename in ['float','double']:
            return C_Basetype("double")
        if type(rtype) == C_Basetype and rtype.typename in ['float','double']:
            return C_Basetype("double")
        if astnode.nodeType == "add":
            if type(ltype) == C_Pointer:
                return ltype
            if type(rtype) == C_Pointer:
                return rtype
        elif astnode.nodeType == "sub":
            if type(ltype) == C_Pointer and type(rtype) != C_Pointer:
                return ltype
            if type(rtype) == C_Pointer and type(ltype) != C_Pointer:
                return rtype
        return C_Basetype("long long")
    elif astnode.nodeType in ["assign", "compound_assign"]:
        lhs = astnode.children[0]
        return ast_type(ctx,lhs)
    elif astnode.nodeType == "comma":
        rhs = astnode.children[1]
        return ast_type(ctx,rhs)
    elif astnode.nodeType == "sizeof":
        return C_Basetype("long long")
    elif astnode.nodeType == "attr":
        lhs = astnode.children[0]
        ltype = unpack_C_Var(ast_type(ctx,lhs))
        field_name = astnode.metas[0]
        field_offset, field_type = struct_offset(ltype,field_name)
        return field_type
    elif astnode.nodeType == "ptr_attr":
        lhs = astnode.children[0]
        ltype = unpack_C_Var(ast_type(ctx,lhs))
        if type(ltype) == C_Pointer:
            ltype = ltype.oftype
        field_name = astnode.metas[0]
        field_offset, field_type = struct_offset(ltype,field_name)
        return field_type
    elif astnode.nodeType == "index":
        arr_ast = astnode.children[0]
        idx_ast = astnode.children[1]
        ltype = unpack_C_Var(ast_type(ctx,arr_ast))
        if type(ltype) == C_Pointer:
            return ltype.oftype
        elif type(ltype) == C_Array:
            if len(ltype.dimension) == 1:
                return ltype.oftype
            else:
                return C_Array(ltype.oftype,ltype.dimension[1:])
    elif astnode.nodeType == "cond":
        tast  = astnode.children[1]
        fast  = astnode.children[2]
        ttype = unpack_C_Var(ast_type(ctx,tast))
        ftype = unpack_C_Var(ast_type(ctx,fast))
        if type(ttype) == C_Basetype and ttype.typename in ["float","double"]:
            return C_Basetype("double")
        if type(ftype) == C_Basetype and ftype.typename in ["float","double"]:
            return C_Basetype("double")
        return ttype
    elif astnode.nodeType == "as":
        astype = astnode.metas[0]
        return astype
    elif astnode.nodeType == "addr":
        lhs   = astnode.children[0]
        etype = unpack_C_Var(ast_type(ctx,lhs))
        return C_Pointer(etype)
    elif astnode.nodeType == "deaddr":
        lhs   = astnode.children[0]
        etype = decay(unpack_C_Var(ast_type(ctx,lhs)))
        if type(etype) == C_Pointer:
            return etype.oftype
        return etype # this should be unreachable!

def solve_addr(ctx: CodegenContext,astnode : ASTNode):
    """生成可寻址表达式的字节地址；此处不加载地址指向的标量值。"""
    if astnode.nodeType == "var":
        var_name = astnode.metas[0]
        ast_type(ctx, astnode)  # Report an undefined identifier before looking up storage.
        var_section , var_pos = ctx.allocator.get(var_name)
        if var_section == "stack":
            ctx.image.extend(i64(opcode["LEA"]) + i64(var_pos))
        elif var_section == "image":
            ctx.image.extend(i64(opcode["IMM"]) + i64(var_pos))
    elif astnode.nodeType == "index":
        etype = unpack_C_Var(ast_type(ctx,astnode.children[0]))
        if etype is None: # if failed when inferencing , use long long 
            etype = C_Basetype("long long")
        if type(etype) == C_Pointer:
            childtype = etype.oftype
        elif type(etype) == C_Array:
            if len(etype.dimension) == 1:
                childtype = etype.oftype
            else:
                childtype = C_Array(etype.oftype,etype.dimension[1:])
        childsize = type_size(childtype)
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        if type(etype) == C_Pointer:
            # lhs is a pointer value; evaluating it directly handles
            # non-addressable expressions such as casts
            codegen_action(ctx,lhs)
        else:
            solve_addr(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["PSH"]))
        ctx.image.extend(i64(opcode["IMM"]) + i64(childsize))
        ctx.image.extend(i64(opcode["MUL"]))
        ctx.image.extend(i64(opcode["ADD"]))
    elif astnode.nodeType == "deaddr":
        codegen_action(ctx,astnode.children[0])
    elif astnode.nodeType == "attr":
        field_name = astnode.metas[0]
        lhs = astnode.children[0]
        solve_addr(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        etype = unpack_C_Var(ast_type(ctx,lhs))
        field_offset , field_type = struct_offset(etype,field_name)
        ctx.image.extend(i64(opcode["IMM"]) + i64(field_offset))
        ctx.image.extend(i64(opcode["ADD"]))
    elif astnode.nodeType == "ptr_attr":
        field_name = astnode.metas[0]
        lhs = astnode.children[0]
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        etype = unpack_C_Var(ast_type(ctx,lhs)).oftype
        field_offset , field_type = struct_offset(etype,field_name)
        ctx.image.extend(i64(opcode["IMM"]) + i64(field_offset))
        ctx.image.extend(i64(opcode["ADD"]))
    elif astnode.nodeType == "string":
        literal_str = astnode.metas[0]
        var_pos = ctx.literalpool.alloc(literal_str) # shall only be on image
        ctx.image.extend(i64(opcode["IMM"]) + i64(var_pos))
    else:
        raise ValueError(f"expression is not assignable: {astnode.nodeType}")

def codegen_action(ctx : CodegenContext,astnode : ASTNode):
    if astnode is None:
        return

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
                ast_type(ctx, func_ast)
                bktype , func_pos = ctx.allocator.get(func_name)
                if bktype == "stack":
                    ctx.image.extend(i64(opcode["LEA"]) + i64(func_pos))
                    ctx.image.extend(i64(opcode["LI"])  + i64(opcode["JSRR"]))
                    ctx.image.extend(i64(opcode["ADJ"]) + i64(len(args_asts)))
                elif bktype == "image":
                    function_type = unpack_C_Var(ast_type(ctx, func_ast))
                    if type(function_type) == C_Func:
                        ctx.image.extend(i64(opcode["JSR"]) + i64(func_pos))
                    else:
                        codegen_action(ctx, func_ast)
                        ctx.image.extend(i64(opcode["JSRR"]))
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
    
    elif astnode.nodeType == "integer":
        literal = astnode.metas[0]
        ctx.image.extend(i64(opcode["IMM"]) + i64(literal))

    elif astnode.nodeType == "float":
        literal = astnode.metas[0]
        ctx.image.extend(i64(opcode["IMM"]) + f64(literal))

    elif astnode.nodeType == "var":
        var_type = ast_type(ctx, astnode)
        if type(var_type) == C_Const:
            ctx.image.extend(i64(opcode["IMM"]) + i64(var_type.value))
        else:
            solve_addr(ctx, astnode)
            load_value(ctx, unpack_C_Var(var_type))

    elif astnode.nodeType == "add":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        ltype = decay(unpack_C_Var(ast_type(ctx,lhs)))
        rtype = decay(unpack_C_Var(ast_type(ctx,rhs)))

        ltype_is_pointer = type(ltype) == C_Pointer
        rtype_is_pointer = type(rtype) == C_Pointer
        ltype_is_double  = type(ltype) == C_Basetype and ltype.typename in ["float","double"]
        rtype_is_double  = type(rtype) == C_Basetype and rtype.typename in ["float","double"] 
        
        if ltype_is_pointer:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            elemsize = type_size(ltype.oftype)
            ctx.image.extend(i64(opcode["PSH"]))
            ctx.image.extend(i64(opcode["IMM"]) + i64(elemsize))
            ctx.image.extend(i64(opcode["MUL"]) + i64(opcode["ADD"]))
        elif rtype_is_pointer:
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,lhs)
            elemsize = type_size(rtype.oftype)
            ctx.image.extend(i64(opcode["PSH"]))
            ctx.image.extend(i64(opcode["IMM"]) + i64(elemsize))
            ctx.image.extend(i64(opcode["MUL"]) + i64(opcode["ADD"]))
        elif ltype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            if not rtype_is_double:
                ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["FADD"]))
        elif rtype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["FADD"]))
        else:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["ADD"]))

    elif astnode.nodeType == "sub":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        ltype = unpack_C_Var(ast_type(ctx,lhs))
        rtype = unpack_C_Var(ast_type(ctx,rhs))

        ltype_is_pointer = type(ltype) == C_Pointer
        rtype_is_pointer = type(rtype) == C_Pointer
        ltype_is_double  = type(ltype) == C_Basetype and ltype.typename in ["float","double"]
        rtype_is_double  = type(rtype) == C_Basetype and rtype.typename in ["float","double"] 
        
        if ltype_is_pointer and rtype_is_pointer:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["SUB"]) + i64(opcode["PSH"]))
            ctx.image.extend(i64(opcode["IMM"]) + i64(type_size(ltype.oftype)) + i64(opcode["DIV"]))
        elif ltype_is_pointer:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            elemsize = type_size(ltype.oftype)
            ctx.image.extend(i64(opcode["PSH"]))
            ctx.image.extend(i64(opcode["IMM"]) + i64(elemsize))
            ctx.image.extend(i64(opcode["MUL"]) + i64(opcode["SUB"]))
        elif rtype_is_pointer:
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,lhs)
            elemsize = type_size(rtype.oftype)
            ctx.image.extend(i64(opcode["PSH"]))
            ctx.image.extend(i64(opcode["IMM"]) + i64(elemsize))
            ctx.image.extend(i64(opcode["MUL"]) + i64(opcode["SUB"]))
        elif ltype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            if not rtype_is_double:
                ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["FSUB"]))
        elif rtype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["FSUB"]))
        else:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["SUB"]))

    elif astnode.nodeType == "mul":
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        ltype = unpack_C_Var(ast_type(ctx,lhs))
        rtype = unpack_C_Var(ast_type(ctx,rhs))

        ltype_is_double  = type(ltype) == C_Basetype and ltype.typename in ["float","double"]
        rtype_is_double  = type(rtype) == C_Basetype and rtype.typename in ["float","double"] 

        if ltype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            if not rtype_is_double:
                ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["FMUL"]))
        elif rtype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["FMUL"]))
        else:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["MUL"]))

    elif astnode.nodeType == "div":
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        ltype = unpack_C_Var(ast_type(ctx,lhs))
        rtype = unpack_C_Var(ast_type(ctx,rhs))

        ltype_is_double  = type(ltype) == C_Basetype and ltype.typename in ["float","double"]
        rtype_is_double  = type(rtype) == C_Basetype and rtype.typename in ["float","double"] 

        if ltype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            if not rtype_is_double:
                ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["FDIV"]))
        elif rtype_is_double:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["I2F"]))
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["FDIV"]))
        else:
            codegen_action(ctx,lhs)
            ctx.image.extend(i64(opcode["PSH"]))
            codegen_action(ctx,rhs)
            ctx.image.extend(i64(opcode["DIV"]))

    elif astnode.nodeType == "mod":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["MOD"]))

    elif astnode.nodeType == "shl":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["SHL"]))

    elif astnode.nodeType == "shr":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["SHR"]))

    elif astnode.nodeType == "bitand":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["AND"]))

    elif astnode.nodeType == "bitor":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["OR"]))

    elif astnode.nodeType == "bitxor":
        lhs = astnode.children[0]
        rhs = astnode.children[1]

        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode["XOR"]))

    elif astnode.nodeType == "bitnot":
        lhs = astnode.children[0]
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["NOT"]))

    elif astnode.nodeType == "neg":
        lhs = astnode.children[0]

        ctx.image.extend(i64(opcode["IMM"]) + i64(0) + i64(opcode["PSH"]))
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["FSUB" if is_floating(unpack_C_Var(ast_type(ctx,lhs))) else "SUB"]))

    elif astnode.nodeType in ["eq","ne","lt","gt","le","ge"]:
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        if any(is_floating(unpack_C_Var(ast_type(ctx, operand))) for operand in [lhs, rhs]):
            raise ValueError("floating-point comparisons are not implemented")
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)
        ctx.image.extend(i64(opcode[astnode.nodeType.upper()]))

    elif astnode.nodeType == "and":
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["BZ"]))
        bz_pos = ctx.image.extend(i64(0))
        codegen_action(ctx,rhs)
        ctx.image.block[bz_pos:bz_pos + 8] = i64(len(ctx.image.block))
        normalize_bool(ctx)

    elif astnode.nodeType == "or":
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["BNZ"]))
        bz_pos = ctx.image.extend(i64(0))
        codegen_action(ctx,rhs)
        ctx.image.block[bz_pos:bz_pos + 8] = i64(len(ctx.image.block))
        normalize_bool(ctx)

    elif astnode.nodeType == "not":
        lhs = astnode.children[0]
        ctx.image.extend(i64(opcode["IMM"]) + i64(0) + i64(opcode["PSH"]))
        codegen_action(ctx,lhs)
        ctx.image.extend(i64(opcode["EQ"]))

    elif astnode.nodeType == "comma":
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        codegen_action(ctx,lhs)
        codegen_action(ctx,rhs)

    elif astnode.nodeType == "deaddr":
        lhs   = astnode.children[0]
        etype = unpack_C_Var(ast_type(ctx,astnode))
        codegen_action(ctx,lhs)
        load_value(ctx, etype)

    elif astnode.nodeType == "addr":
        lhs   = astnode.children[0]
        solve_addr(ctx,lhs)

    elif astnode.nodeType == "index":
        solve_addr(ctx,astnode)
        var_type = unpack_C_Var(ast_type(ctx,astnode))
        load_value(ctx, var_type)

    elif astnode.nodeType == "actions":
        codegen_actions(ctx,astnode)

    elif astnode.nodeType == "sizeof":
        sztype = astnode.metas[0] if astnode.metas else unpack_C_Var(ast_type(ctx, astnode.children[0]))
        size = type_size(sztype)
        ctx.image.extend(i64(opcode["IMM"]) + i64(size))

    elif astnode.nodeType == "ret":
        if astnode.children[0] is not None:
            codegen_action(ctx,astnode.children[0])
        ctx.image.extend(i64(opcode["LEV"]))

    elif astnode.nodeType == "attr":
        solve_addr(ctx,astnode)
        etype = unpack_C_Var(ast_type(ctx,astnode))
        load_value(ctx, etype)

    elif astnode.nodeType == "ptr_attr":
        solve_addr(ctx,astnode)
        etype = unpack_C_Var(ast_type(ctx,astnode))
        load_value(ctx, etype)

    elif astnode.nodeType in ["cond","ifelse"] :
        cond_ast , tast , fast = astnode.children
        floating_result = astnode.nodeType == "cond" and is_floating(ast_type(ctx, astnode))
        codegen_action(ctx,cond_ast)
        ctx.image.extend(i64(opcode["BZ"]))
        fpos  = ctx.image.extend(i64(0))
        codegen_action(ctx,tast)
        if floating_result and not is_floating(unpack_C_Var(ast_type(ctx, tast))):
            ctx.image.extend(i64(opcode["I2F"]))
        ctx.image.extend(i64(opcode["JMP"]))
        tpos  = ctx.image.extend(i64(0))
        fdest = len(ctx.image.block)
        codegen_action(ctx,fast)
        if floating_result and not is_floating(unpack_C_Var(ast_type(ctx, fast))):
            ctx.image.extend(i64(opcode["I2F"]))
        tdest = len(ctx.image.block)

        ctx.image.block[fpos:fpos+8] = i64(fdest)
        ctx.image.block[tpos:tpos+8] = i64(tdest)

    elif astnode.nodeType == "if":
        cond_ast , branch = astnode.children
        codegen_action(ctx,cond_ast)
        ctx.image.extend(i64(opcode["BZ"]))
        fpos  = ctx.image.extend(i64(0))
        codegen_action(ctx,branch)
        ctx.image.block[fpos:fpos+8] = i64(len(ctx.image.block))

    elif astnode.nodeType in ["incret", "decret", "retinc", "retdec"]:
        target = astnode.children[0]
        target_type = unpack_C_Var(ast_type(ctx,target))
        solve_addr(ctx,target)
        ctx.image.extend(i64(opcode["PSH"]))
        load_value(ctx, target_type)
        ctx.image.extend(i64(opcode["PSH"]))
        step = type_size(target_type.oftype) if type(target_type) == C_Pointer else 1
        floating = is_floating(target_type)
        ctx.image.extend(i64(opcode["IMM"]) + (f64(1.0) if floating else i64(step)))
        increasing = astnode.nodeType in ["incret", "retinc"]
        operation = ("F" if floating else "") + ("ADD" if increasing else "SUB")
        ctx.image.extend(i64(opcode[operation]))
        ctx.image.extend(i64(opcode["SC" if is_byte(target_type) else "SI"]))
        if astnode.nodeType in ["retinc", "retdec"]:
            ctx.image.extend(i64(opcode["PSH"]) + i64(opcode["IMM"]) + (f64(1.0) if floating else i64(step)))
            inverse = ("F" if floating else "") + ("SUB" if increasing else "ADD")
            ctx.image.extend(i64(opcode[inverse]))
        if is_byte(target_type):
            normalize_byte(ctx, target_type)

    elif astnode.nodeType == "as":
        child       = astnode.children[0]
        codegen_action(ctx,child)
        target_type = astnode.metas[0]
        etype       = unpack_C_Var(ast_type(ctx,child))
        if type(etype) == C_Basetype and etype.typename in ["float","double"]:
            if type(target_type) == C_Basetype and target_type.typename not in ["float","double"]:
                ctx.image.extend(i64(opcode["F2I"]))
        else:
            if type(target_type) == C_Basetype and target_type.typename in ["float","double"]:
                ctx.image.extend(i64(opcode["I2F"]))

    elif astnode.nodeType == "break":
        if ctx.flowCtx is None:
            raise ValueError("break outside loop")
        if ctx.flowCtx is not None:
            ctx.image.extend(i64(opcode["JMP"]))
            brk_pos = ctx.image.extend(i64(0))
            ctx.flowCtx.break_pos_lst.append(brk_pos)

    elif astnode.nodeType == "continue":
        if ctx.flowCtx is None:
            raise ValueError("continue outside loop")
        if ctx.flowCtx is not None:
            ctx.image.extend(i64(opcode["JMP"]))
            cont_pos = ctx.image.extend(i64(0))
            ctx.flowCtx.continue_pos_lst.append(cont_pos)

    elif astnode.nodeType == "while":
        cond_ast , loop_ast = astnode.children
        loop_dest = len(ctx.image.block)
        codegen_action(ctx,cond_ast)

        # create a new flowContext
        ctx = CodegenContext(
            ctx.image,ctx.literalpool,ctx.allocator,ctx.symtable,
            FlowContext([],[])
        )

        ctx.image.extend(i64(opcode["BZ"]))
        exit_pos  = ctx.image.extend(i64(0))
        codegen_action(ctx,loop_ast)
        ctx.image.extend(i64(opcode["JMP"]))
        ctx.image.extend(i64(loop_dest))
        exit_dest = len(ctx.image.block)
        ctx.image.block[exit_pos:exit_pos + 8] = i64(exit_dest)

        for cont_pos in ctx.flowCtx.continue_pos_lst:
            ctx.image.block[cont_pos: cont_pos + 8] = i64(loop_dest)

        for brk_pos in ctx.flowCtx.break_pos_lst:
            ctx.image.block[brk_pos: brk_pos + 8] = i64(exit_dest)

    elif astnode.nodeType == "do_while":
        cond_ast , loop_ast = astnode.children
        
        oldctx = ctx
        ctx = CodegenContext(
            ctx.image,ctx.literalpool,ctx.allocator,ctx.symtable,
            FlowContext([],[])
        )

        loop_dest = len(ctx.image.block)
        codegen_action(ctx,loop_ast)
        cond_dest = len(ctx.image.block)
        codegen_action(oldctx,cond_ast)
        ctx.image.extend(i64(opcode["BNZ"]))
        ctx.image.extend(i64(loop_dest))
        exit_dest = len(ctx.image.block)

        for cont_pos in ctx.flowCtx.continue_pos_lst:
            ctx.image.block[cont_pos: cont_pos + 8] = i64(cond_dest)

        for brk_pos in ctx.flowCtx.break_pos_lst:
            ctx.image.block[brk_pos: brk_pos + 8] = i64(exit_dest)

    elif astnode.nodeType == "for":
        init_ast , cond_ast , inc_ast , loop_ast = astnode.children
        
        oldctx = ctx
        ctx = CodegenContext(
            ctx.image,ctx.literalpool,ctx.allocator,ctx.symtable,
            FlowContext([],[])
        )

        codegen_action(oldctx,init_ast)
        loop_dest = len(ctx.image.block)
        codegen_action(oldctx,cond_ast)
        ctx.image.extend(i64(opcode["BZ"]))
        exit_pos  = ctx.image.extend(i64(0))
        codegen_action(ctx,loop_ast)
        inc_dest  = len(ctx.image.block)
        codegen_action(oldctx,inc_ast)
        ctx.image.extend(i64(opcode["JMP"]))
        ctx.image.extend(i64(loop_dest))
        exit_dest = len(ctx.image.block)
        ctx.image.block[exit_pos:exit_pos + 8] = i64(exit_dest)

        for cont_pos in ctx.flowCtx.continue_pos_lst:
            ctx.image.block[cont_pos: cont_pos + 8] = i64(inc_dest)

        for brk_pos in ctx.flowCtx.break_pos_lst:
            ctx.image.block[brk_pos: brk_pos + 8] = i64(exit_dest)


    elif astnode.nodeType == "init_assign":
        var_ast : ASTNode = astnode.children[0]
        lst_ast : ASTNode = astnode.children[1]

        var_name = var_ast.metas[0]
        var_type_type , var_type = ctx.symtable.get((var_name,))
        var_type = var_type.oftype
        var_section   , var_pos  = ctx.allocator.get(var_name)# var_section shall only be stack here
        initlst  = lst_ast.metas[0]
        # C aggregate initialization zero-fills every omitted element, including
        # a reused local stack frame.
        ctx.image.extend(i64(opcode["LEA"]) + i64(var_pos) + i64(opcode["PSH"]))
        ctx.image.extend(i64(opcode["IMM"]) + i64(0) + i64(opcode["PSH"]))
        ctx.image.extend(i64(opcode["IMM"]) + i64(type_size(var_type)) + i64(opcode["PSH"]))
        ctx.image.extend(i64(opcode["MSET"]) + i64(opcode["ADJ"]) + i64(3))

        def assign_element(var_type : Any,val_ast : ASTNode,var_pos : int):
            if type(var_type) == C_Basetype and var_type.typename in ["unsigned char","char","signed char"]:
                ctx.image.extend(i64(opcode["LEA"]) + i64(var_pos))
                ctx.image.extend(i64(opcode["PSH"]))
                codegen_action(ctx,val_ast)
                ctx.image.extend(i64(opcode["SC"]))
            else:
                ctx.image.extend(i64(opcode["LEA"]) + i64(var_pos))
                ctx.image.extend(i64(opcode["PSH"]))
                codegen_action(ctx,val_ast)
                ctx.image.extend(i64(opcode["SI"]))

        def init_assign(var_type: Any,content: list[tuple],var_pos: int):
            if type(var_type) == C_Array:
                if len(var_type.dimension) == 1:
                    childtype = var_type.oftype
                else:
                    childtype = C_Array(var_type.oftype,var_type.dimension[1:])
                childsize = type_size(childtype)
                for idx,elemast in content:
                    if not 0 <= idx < var_type.dimension[0]:
                        raise ValueError("array initializer exceeds declared size")
                    elemast : ASTNode # should be a "initlist"
                    if elemast.nodeType == "initlist":
                        init_assign(childtype,elemast.metas[0],var_pos + idx * childsize)
                    else:
                        init_assign(childtype,elemast,var_pos + idx * childsize)
            elif type(var_type) == C_Struct:
                for idx,elemast in content:
                    if type(idx) == int:
                        field_offset , field_type = struct_idx_offset(var_type,idx)
                    elif type(idx) == str:
                        field_offset , field_type = struct_offset(var_type,idx)
                    if elemast.nodeType == "initlist":
                        initlst = elemast.metas[0]
                        init_assign(field_type,initlst,var_pos + field_offset)
                    else:
                        init_assign(field_type,elemast,var_pos + field_offset)
            else:
                if isinstance(content, list):
                    if len(content) > 1:
                        raise ValueError("too many scalar initializers")
                    content = content[0][1] if content else ASTNode("integer", [], (0,))
                assign_element(var_type,content,var_pos)        
        
        init_assign(var_type,initlst,var_pos)

    elif astnode.nodeType == "assign":
        lhs = astnode.children[0]
        rhs = astnode.children[1]
        lhs_type = unpack_C_Var(ast_type(ctx,lhs))
        if type(lhs_type) in [C_Array, C_Struct, C_Union]:
            raise ValueError("aggregate assignment is not implemented; use brace initializers or memcpy")
        rhs_type = unpack_C_Var(ast_type(ctx, rhs))
        if is_floating(lhs_type) != is_floating(rhs_type):
            raise ValueError("implicit float/integer conversion is not implemented; use an explicit cast")

        solve_addr(ctx,lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        codegen_action(ctx,rhs)

        lhs_type = unpack_C_Var(ast_type(ctx,lhs))
        if lhs_type is None or type(lhs_type) == C_Basetype and lhs_type.typename in ["unsigned char","char","signed char"]:
            ctx.image.extend(i64(opcode["SC"]))
        else:
            ctx.image.extend(i64(opcode["SI"]))

    elif astnode.nodeType == "compound_assign":
        lhs, rhs = astnode.children
        lhs_type = unpack_C_Var(ast_type(ctx, lhs))
        solve_addr(ctx, lhs)
        ctx.image.extend(i64(opcode["PSH"]))
        load_value(ctx, lhs_type)
        # The lvalue address and its value have already been evaluated once.
        cached = ASTNode("cached_value", [], (lhs_type,))
        codegen_action(ctx, ASTNode(astnode.metas[0], [cached, rhs], ()))
        ctx.image.extend(i64(opcode["SC" if is_byte(lhs_type) else "SI"]))
    elif astnode.nodeType == "cached_value":
        return
    else:
        raise ValueError(f"unsupported AST node: {astnode.nodeType}")

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
    """VM ABI：字符为 1 字节，其余标量为 8 字节；结构体字段紧密排列。"""
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
            if not isinstance(d, int) or d <= 0:
                raise ValueError("array dimensions must be explicit positive integers")
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
        if var_type.typename in ["char", "signed char", "unsigned char"]:
            return 1
        return 8
    assert False # unreachable

def struct_offset(struct_type : C_Struct,field_name : str):
    offset = 0
    for field_type, struct_field_name in struct_type.fields:
        if struct_field_name == field_name:
            return (0 if type(struct_type) == C_Union else offset), field_type
        offset += type_size(field_type)
    raise ValueError(f"unknown member: {field_name}")

def struct_idx_offset(struct_type : C_Struct,idx : int):
    offset = 0
    for i , (field_type, _) in enumerate(struct_type.fields):
        if i == idx:
            return offset , field_type
        offset += type_size(field_type)
    raise ValueError(f"initializer member index out of range: {idx}")

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
        if node is None:
            return
        if node.nodeType == "sizeof":
            return
        if node.nodeType == "string":
            ctx.literalpool.alloc(node.metas[0])
        if node.nodeType == "initlist":
            for _,ast in node.metas[0]:
                if type(ast) == ASTNode:
                    traverse(ast)
        for child in node.children:
            traverse(child)
    traverse(astnode)

def constant_value(ctx, node):
    if node.nodeType == "sizeof":
        var_type = node.metas[0] if node.metas else unpack_C_Var(ast_type(ctx, node.children[0]))
        return type_size(var_type)
    if node.nodeType in ["integer", "float"]:
        return node.metas[0]
    if node.nodeType == "string":
        return ctx.literalpool.alloc(node.metas[0])
    if node.nodeType == "var":
        var_type = ast_type(ctx, node)
        if type(var_type) == C_Const:
            return var_type.value
        if type(unpack_C_Var(var_type)) == C_Func:
            return ctx.allocator.get(node.metas[0])[1]
    if node.nodeType == "neg":
        return -constant_value(ctx, node.children[0])
    if node.nodeType == "bitnot":
        return ~constant_value(ctx, node.children[0])
    if node.nodeType in ["add", "sub", "mul", "div", "mod", "shl", "shr", "bitand", "bitor", "bitxor"]:
        left, right = [constant_value(ctx, child) for child in node.children]
        if node.nodeType in ["div", "mod"]:
            if right == 0:
                raise ValueError("division by zero in constant initializer")
            quotient = (abs(left) // abs(right)) * (-1 if (left < 0) != (right < 0) else 1)
            if node.nodeType == "mod":
                return left - quotient * right
            return left / right if isinstance(left, float) or isinstance(right, float) else quotient
        import operator
        operation = {"add": operator.add, "sub": operator.sub, "mul": operator.mul,
                     "shl": operator.lshift, "shr": operator.rshift, "bitand": operator.and_,
                     "bitor": operator.or_, "bitxor": operator.xor}[node.nodeType]
        return operation(left, right)
    raise ValueError(f"unsupported static initializer: {node.nodeType}")


def static_init(ctx : CodegenContext, astroot : ASTNode):

    def assign_element(var_type,literal_ast,var_pos):
        if literal_ast.nodeType == "string" and type(var_type) == C_Array:
            data = literal_ast.metas[0].encode("utf-8")
            if len(data) > type_size(var_type):
                raise ValueError("string initializer exceeds array size")
            ctx.image.block[var_pos:var_pos + len(data)] = data
            return
        value = constant_value(ctx, literal_ast)
        if is_floating(var_type):
            data = f64(value)
        elif is_byte(var_type):
            data = u8(int(value) & 255)
        else:
            data = i64(int(value))
        ctx.image.block[var_pos:var_pos + len(data)] = data

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
                        if not 0 <= idx < var_type.dimension[0]:
                            raise ValueError("array initializer exceeds declared size")
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
                    if isinstance(content, list):
                        if len(content) > 1:
                            raise ValueError("too many scalar initializers")
                        content = content[0][1] if content else ASTNode("integer", [], (0,))
                    assign_element(var_type,content,var_pos)

            init_assign(var_type,initlist,var_pos)
