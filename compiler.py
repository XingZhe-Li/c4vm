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
    print(tokens)

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