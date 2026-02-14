import re
import os
import sys
from dataclasses import dataclass

def c4vm_c_preprocess_remove_comment(src: str) -> str:
    idx = 0 ; out = []
    while idx < len(src):
        if src[idx] == '/':
            idx += 1
            if idx < len(src) and src[idx] == '/':
                while idx < len(src) and src[idx] != '\n':
                    idx += 1
                continue
            elif idx < len(src) and src[idx] == '*':
                idx += 1
                while idx < len(src):
                    while idx < len(src) and src[idx] != '*':
                        idx += 1
                    idx += 1
                    if idx < len(src) and src[idx] == '/':
                        idx += 1
                        break
                continue
            else:
                idx -= 1
        out.append(src[idx])
        idx += 1
    return ''.join(out)

def c4vm_c_preprocess_include(src: str, src_path_root: str) -> str:
    buffer = []
    for ln in src.split('\n'):
        if ln.startswith("#include"):
            ln = ln.removeprefix("#include").strip()
            includes = [i.group(1) for i in re.finditer(r'\"(.*?)\"',ln)] # <stdio.h> would be ignored
            for fname in includes:
                if not os.path.isfile(src_path_root + '/' + fname):
                    print("[WARN] c4vm_c_preprocess_include : {0} is not found when including".format(fname))
                try:
                    with open(src_path_root + '/' + fname) as f:
                        child_src = f.read()
                except Exception as e:
                    print(e)
                    print("[ERRO] c4vm_c_preprocess_include : failed when opening {0} ".format(src_path_root + '/' + fname))
                    sys.exit(1)
                child_src = c4vm_c_preprocess(child_src,os.path.dirname(src_path_root + '/' + fname))
                buffer.append(child_src)
            continue
        buffer.append(ln)
    return '\n'.join(buffer)

def c4vm_c_preprocess_defines(src: str):
    buffer = []
    state_stack = []
    define_table = {}

    for ln in src.split('\n'):
        raw_ln = ln
        ln_strip = ln.strip()
        
        if ln_strip.startswith("#"):
            lnsplit = ln_strip.split()
            cmd = lnsplit[0]
            
            if cmd == "#define":
                if len(lnsplit) == 2:
                    define_table[lnsplit[1]] = ""
                elif len(lnsplit) >= 3:
                    define_table[lnsplit[1]] = " ".join(lnsplit[2:])
                continue
                
            elif cmd == "#undef":
                define_table.pop(lnsplit[1], None)
                continue
                
            elif cmd == "#ifdef":
                active = (lnsplit[1] in define_table)
                state_stack.append(active)
                continue

            elif cmd == "#ifndef":
                active = (lnsplit[1] not in define_table)
                state_stack.append(active)
                continue

            elif cmd == "#else":
                if state_stack:
                    state_stack[-1] = not state_stack[-1]
                continue

            elif cmd == "#endif":
                if state_stack:
                    state_stack.pop()
                continue

        if all(state_stack):
            processed_ln = raw_ln
            if define_table:
                for name in sorted(define_table.keys(), key=len, reverse=True):
                    pattern = r'\b' + re.escape(name) + r'\b'
                    processed_ln = re.sub(pattern, str(define_table[name]), processed_ln)
            
            buffer.append(processed_ln)

    return "\n".join(buffer)

def c4vm_c_preprocess(src: str,src_path_root: str):
    src = c4vm_c_preprocess_remove_comment(src)
    src = c4vm_c_preprocess_include(src,src_path_root)
    src = c4vm_c_preprocess_defines(src)
    return src
    
@dataclass
class Token:
    type: str   # KEYWORD, ID, NUM, STR, OP
    value: str
    line: int

def c4vm_c_lexer(src: str) -> list[Token]:
    token_specs = [
        ('NUM',     r'\d+'),                   
        ('STR',     r'"(.*?(?<!\\))"'),        
        ('KEYWORD', r'\b(int|char|long|if|else|while|return|void|sizeof)\b'),
        ('ID',      r'[a-zA-Z_][a-zA-Z0-9_]*'),
        ('OP',      r'==|!=|<=|>=|&&|\|\||[+\-*/%&|^=<>!~(){}\[\];,]'),
        ('NEWLINE', r'\n'),                    
        ('SKIP',    r'[ \t\r]+'),             
        ('MISMATCH',r'.'),                     
    ]

    tok_regex = '|'.join('(?P<%s>%s)' % pair for pair in token_specs)
    line_num = 1
    tokens = []

    for mo in re.finditer(tok_regex, src):
        kind = mo.lastgroup
        value = mo.group()
        
        if kind == 'NUM':
            tokens.append(Token('NUM', value, line_num))
        elif kind == 'STR':
            tokens.append(Token('STR', value[1:-1], line_num))
        elif kind == 'KEYWORD':
            tokens.append(Token('KEYWORD', value, line_num))
        elif kind == 'ID':
            tokens.append(Token('ID', value, line_num))
        elif kind == 'OP':
            tokens.append(Token('OP', value, line_num))
        elif kind == 'NEWLINE':
            line_num += 1
        elif kind == 'SKIP':
            continue
        elif kind == 'MISMATCH':
            print(f"[ERRO] Lexer: Unexpected character '{value}' at line {line_num}")
            sys.exit(1)
            
    return tokens

def c4vm_c_compile_to_bytecode(tokens: list[Token]):
    class OPCODES:
        NOP = 0;LEA = 1;IMM = 2;JMP = 3;JSR = 4;BZ = 5;BNZ = 6;ENT = 7;ADJ = 8;LEV = 9;LI = 10
        LC = 11;SI = 12;SC = 13;PSH = 14;OR = 15;XOR = 16;AND = 17;EQ = 18;NE = 19;LT = 20
        GT = 21;LE = 22;GE = 23;SHL = 24;SHR = 25;ADD = 26;SUB = 27;MUL = 28;DIV = 29;MOD = 30
        OPEN = 31;READ = 32;CLOS = 33;PRTF = 34;MALC = 35;FREE = 36;MSET = 37;MCMP = 38;EXIT = 39;SCMP = 40
        SLEN = 41;SSTR = 42;SCAT = 43

    class DataTypes:
        class Char:
            pass
        class LongLong:
            pass
        class CompoundType:
            def __init__(self,ofType,pointer_level: int = 0,array_len: int = None):
                self.ofType        = ofType
                self.pointer_level = pointer_level
                self.array_len     = array_len

    class RelocateItem:
        def __init__(self,at_target,at,to_target,to):
            '''
            at_target / to_target in ["text","data"].
            at , to should be described in bytes.
            '''
            self.at_target = at_target ; self.to_target = to_target
            self.at = at               ; self.to        = to

    def i2b(x: int):
        return x.to_bytes(8,"little")

    class C4Parser:
        def __init__(self, tokens):
            self.tokens = tokens
            self.pos    = 0

            self.text   = bytearray()
            self.data   = bytearray()
            self.relocs : list[RelocateItem] = []
            self.global_loc = {} # global_loc["name"] = data_offset

        def peek(self):
            return self.tokens[self.pos] if self.pos < len(self.tokens) else None

        def match(self, expected_value=None, expected_type=None):
            tok = self.peek()
            if not tok: return False
            if expected_value and tok.value != expected_value: return False
            if expected_type and tok.type != expected_type: return False
            self.pos += 1
            return tok

        def emit_text(self, content: bytes):
            '''notice this function takes bytes rather than int!!!'''
            for b in content:
                self.text.append(b)

        def emit_data(self, content: bytes):
            '''notice this function takes bytes rather than int!!!'''
            for b in content:
                self.data.append(b)

        def emit_data_longlong(self,value=0) -> int:
            '''return offset'''
            if len(self.data) % 8 != 0:
                self.emit_data(b"\x00" * (8 - len(self.data) % 8))
            self.emit_data(i2b(value))
            return len(self.data) - 8

        def emit_data_string(self,s="") -> int:
            if type(s) == str:
                s = s.encode(encoding='utf-8')
            if s[-1] != b"\x00":
                s += b"\x00"
            start_data_offset = len(self.data)
            self.emit_data(s)
            return start_data_offset

        def rewind(self,pos):
            self.pos = pos

        def getpos(self):
            return self.pos

        def parse(self):
            '''
            planning only to support multiple pointer + 1 dimension array (****arr[8])
            '''

            def atomic_types():
                if self.match("int","KEYWORD"):
                    return DataTypes.LongLong()
                if self.match("long","KEYWORD"):
                    self.match("long","KEYWORD")
                    return DataTypes.LongLong()
                if self.match("void","KEYWORD"):
                    return DataTypes.LongLong()
                if self.match("char","KEYWORD"):
                    return DataTypes.Char()
                return None

            def var_declaration(var_prefix=""):
                snapshot = self.getpos()
                basetype = atomic_types()
                if basetype is None:
                    self.rewind(snapshot)
                    return None
                
                while True:
                    pointer_cnt   = 0
                    array_len     = None
                    variable_name = None

                    while self.match(expected_value="*",expected_type="OP"):
                        pointer_cnt += 1
                    
                    if token := self.match(expected_type="ID"):
                        token : Token
                        variable_name = token.value
                    else:
                        print("[ERRO] unsupported variable type")
                        self.rewind(snapshot)
                        return None
                    
                    if self.match("[","OP"):
                        token = self.match(expected_type="NUM")
                        if not token:
                            print("[ERRO] unsupported inferenced array size")
                            self.rewind(snapshot)
                            return None
                        array_len = int(token.value)
                        if not self.match(expected_value="]",expected_type="OP"):
                            print("[ERRO] mismatched ]")
                            self.rewind(snapshot)
                            return None
                    
                    finalType = basetype
                    if array_len is not None or pointer_cnt != 0:
                        finalType = DataTypes.CompoundType(basetype,pointer_cnt,array_len)

                    if type(finalType) != DataTypes.CompoundType:
                        variable_loc = self.emit_data_longlong()
                        self.global_loc[var_prefix + "$" + variable_name] = variable_loc
                    elif finalType.array_len != None:
                        if type(finalType.ofType) == DataTypes.Char and finalType.pointer_level == 0:
                            variable_loc = self.emit_data_string("\x00" * (finalType.array_len))
                            self.global_loc[var_prefix + "$" + variable_name] = variable_loc
                        else:
                            variable_loc = None
                            for _ in range(finalType.array_len):
                                v = self.emit_data_longlong()
                                if variable_loc == None:
                                    variable_loc = v
                            self.global_loc[var_prefix + "$" + variable_name] = variable_loc
                    else:
                        variable_loc = self.emit_data_longlong()
                        self.global_loc[var_prefix + "$" + variable_name] = variable_loc

                    isCharArray = type(finalType) == DataTypes.CompoundType \
                        and finalType.array_len != None \
                        and finalType.pointer_level == 0 \

                    if self.match("="):
                        if token := self.match(expected_type="STR"):
                            if isCharArray:
                                self.data[variable_loc:variable_loc+len(token.value)] = token.value.encode()
                            else:
                                string_start = self.emit_data_string(token.value)
                                self.relocs.append(
                                    RelocateItem(
                                        at_target = "data",
                                        at = variable_loc,
                                        to_target = "data",
                                        to = string_start
                                    )
                                )
                        elif token := self.match(expected_type="NUM"):
                            self.data[variable_loc:variable_loc+8] = i2b(int(token.value))
                        elif self.match("{","OP"):
                            unit_size = 1 if isCharArray else 8
                            fill_ptr  = variable_loc
                            while token := self.match(expected_type="NUM"):
                                unit_byte = int(token.value).to_bytes(unit_size,'little')
                                self.data[fill_ptr:fill_ptr+unit_size] = unit_byte
                                fill_ptr += unit_size
                                self.match(",","OP")
                            if not self.match("}","OP"):
                                print("[ERRO] unclosed array!")
                                sys.exit(1)
                        else:
                            print("[ERRO] unknown init!")
                            sys.exit(1)

                    if self.match(";"):
                        print("[INFO] parsed variable {0} {1} {2}".format(variable_name,finalType,variable_loc))
                        return None
                    elif self.match(","):
                        print("[INFO] parsed variable {0} {1} {2}".format(variable_name,finalType,variable_loc))
                        continue
                    else:
                        print("[ERRO] expecting ; var parse failed")
                        self.rewind(snapshot)
                        return None

            def func_declaration():
                snapshot = self.getpos()
                basetype = atomic_types()
                if basetype is None:
                    print("[WARN] basetype mismatch!")
                    self.rewind(snapshot)
                    return None
                ...

            def global_declarations():
                while self.peek():
                    start_pos = self.getpos()
                    var_declaration()
                    func_declaration()
                    end_pos   = self.getpos()
                    if self.peek() and end_pos == start_pos:
                        print("[ERRO] failed to parse!")
                        sys.exit(1)

            global_declarations()

        def pack(self): 
            '''merge sections'''
            
            if len(self.text) % 8 != 0:
                self.text.append(b"\x00" * (8 - len(self.text) % 8))

            image = self.text + self.data
            text_size = len(self.text)

            for reloc_item in self.relocs:
                reloc_item : RelocateItem
                at_target = reloc_item.at_target
                at = reloc_item.at
                to_target = reloc_item.to_target
                to = reloc_item.to

                at_absolute = at if at_target == "text" else text_size + at
                to_absolute = to if to_target == "text" else text_size + to

                image[at_absolute:at_absolute+8] = i2b(to_absolute)
            
            return bytes(image)

    parser = C4Parser(tokens)
    parser.parse()
    return parser.pack()

def c4vm_c_compile(src_entry):
    if not os.path.isfile(src_entry):
        print("[ERRO] c4vm_c_compile : {0} does not exist".format(src_entry))
        sys.exit(1)
    src_path_root = os.path.dirname(src_entry)
    try:
        with open(src_entry,'r',encoding='utf-8') as f:
            src = f.read()
    except Exception as e:
        print(e)
        print("[ERRO] c4vm_c_compile : failed when opening {0}".format(src_entry))
        sys.exit(1)
    src = c4vm_c_preprocess(src,src_path_root)
    tokens = c4vm_c_lexer(src)
    return c4vm_c_compile_to_bytecode(tokens)

def c4vm_pack(program_bytes,space: int):
    return space.to_bytes(8,'little') + program_bytes

def pack_to_file(packed_bytes,target_path):
    try:
        with open(target_path,"wb") as f:
            f.write(packed_bytes)
        print('[INFO] pack_to_file : output to {0}'.format(target_path))
    except Exception as e:
        print(e)
        print("[ERRO] pack_to_file : failed when saving to {0}".format(target_path))
        sys.exit(1)

if __name__ == '__main__':
    # change to this directory
    os.chdir(os.path.dirname(__file__))
    
    # compile process
    src_entry       = './test.c'
    program_bytes   = c4vm_c_compile(src_entry)
    # packed_bytes    = c4vm_pack(program_bytes,space=1*1024*1024)
    # pack_to_file(packed_bytes,"./c4vm.image")