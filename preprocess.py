import re
import os
import lexer
from common import Token

def entry(tokens: list[Token],cwd: str) -> list[Token]:
    including_stack  = []
    define_table     = {}
    return preprocess(tokens,define_table,including_stack,cwd)

def handle_macro(
        macro_line: str,
        define_table:dict[str,str],
        including_stack:list[bool],
        output_tokens: list[Token],
        cwd: str) -> int:
    
    macro_line = macro_line.strip()
    if matchobj := re.match(r'^include\s+(<.*?>|".*?")$',macro_line):
        # include clause
        include_target = matchobj.group(1)
        if include_target.startswith("<"):
            pass
            # discard internal file inclusion
        elif include_target.startswith("\""):
            include_target = include_target[1:-1]
            target_path = os.path.join(cwd,include_target)
            if os.path.isfile(target_path):
                next_cwd = os.path.dirname(target_path)
                with open(target_path,'r',encoding='utf-8') as f:
                    src = f.read()
                include_tokens    = lexer.tokenize(src)
                preprocess_tokens = preprocess(
                    include_tokens,
                    define_table,
                    including_stack,
                    next_cwd
                )
                output_tokens.extend(preprocess_tokens)
    elif matchobj := re.match(r'^define\s+(\S*)(?:|\s+(.*))$',macro_line):
        # define clause
        macro_name, macro_replacement = matchobj.groups()
        if macro_name in define_table:
            print("{0} is already declared".format(macro_name))
        macro_replacement = lexer.tokenize(macro_replacement) if macro_replacement else None
        define_table[macro_name] = macro_replacement
    elif matchobj := re.match(r'^undef\s+(\S*)$',macro_line):
        # undef clause
        macro_name = matchobj.group(1)
        if macro_name not in define_table:
            print("{0} is not yet defined".format(macro_name))
        del define_table[macro_name]
    elif matchobj := re.match(r'^ifdef\s+(\S*)$',macro_line):
        # ifdef clause
        macro_name = matchobj.group(1)
        active = macro_name in define_table
        including_stack.append(active)
    elif matchobj := re.match(r'^ifndef\s+(\S*)$',macro_line):
        # ifndef clause
        macro_name = matchobj.group(1)
        active = macro_name not in define_table
        including_stack.append(active)
    elif macro_line == "else":
        # else clause
        if including_stack:
            including_stack[-1] = not including_stack[-1]
    elif macro_line == "endif":
        # endif clause
        if including_stack:
            including_stack.pop()
    else:
        print("macro discard \"{0}\"".format(macro_line))

def preprocess(tokens: list[Token], 
               define_table: dict[str,str],
               including_stack: list[bool],
               cwd: str) -> list[Token]:
    '''
    define_table for recursive-including
    including_stack for ifdef & ifndef detection
    '''

    # variable for return
    output_tokens = []

    idx = 0
    while idx < len(tokens):
        tk = tokens[idx]
        if not including_stack or including_stack[-1]:
            if tk.tktype == "macro":
                handle_macro(
                    tk.value,
                    define_table,including_stack,
                    output_tokens,cwd
                )
                idx += 1
            elif tk.tktype == "identifier":
                id_name = tk.value
                if id_name in define_table:
                    macro_replacement = define_table[id_name]
                    output_tokens.extend(macro_replacement)
                    idx += 1
                else:
                    output_tokens.append(tk)
                    idx += 1
            else:
                output_tokens.append(tk)
                idx += 1
        else:
            if tk.tktype == "macro":
                handle_macro(
                    tk.value,
                    define_table,including_stack,
                    output_tokens,cwd
                )
                idx += 1
            else:
                idx += 1

    return output_tokens