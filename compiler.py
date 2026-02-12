import re
import os
import sys

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
    """
    Process C preprocessor directives: #define, #ifdef, #ifndef, #undef, #else, #endif.
    Handles simple macro replacement and conditional compilation.
    """
    lines = src.split('\n')
    defines = {}

    conditional_stack = []
    final_lines = []

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped_line = line.strip()

        if stripped_line.startswith('#ifdef'):
            condition = stripped_line[6:].strip()
            is_defined = condition in defines
            conditional_stack.append(is_defined)
        elif stripped_line.startswith('#ifndef'):
            condition = stripped_line[7:].strip()
            is_defined = condition not in defines
            conditional_stack.append(is_defined)
        elif stripped_line.startswith('#else'):
            if conditional_stack:
                prev_condition_met = conditional_stack.pop()
                else_condition_met = not prev_condition_met
                conditional_stack.append(else_condition_met)
        elif stripped_line.startswith('#endif'):
            if conditional_stack:
                conditional_stack.pop()
        elif stripped_line.startswith('#define'):
            should_include = not conditional_stack or all(include for include in conditional_stack)
            if should_include:
                define_parts = stripped_line[7:].strip().split(None, 1)
                if len(define_parts) >= 1:
                    name = define_parts[0].strip()

                    if len(define_parts) > 1:
                        replacement = define_parts[1].strip()
                    else:
                        replacement = ''
                    defines[name] = replacement
        elif stripped_line.startswith('#undef'):
            should_include = not conditional_stack or all(include for include in conditional_stack)
            if should_include:
                undef_parts = stripped_line[6:].strip().split(None, 1)
                if len(undef_parts) >= 1:
                    name_to_undef = undef_parts[0].strip()
                    if name_to_undef in defines:
                        del defines[name_to_undef]
        else:
            should_include = not conditional_stack or all(include for include in conditional_stack)  # Simplified: single value
            if should_include:
                final_lines.append(line)

        i += 1
    
    def expand_macros_in_text(text):
        """Helper function to expand all simple macros in a given text"""
        expanded_text = text
        prev_text = ""

        while expanded_text != prev_text:
            prev_text = expanded_text
            
            for name, replacement in defines.items():
                pattern = r'\b' + re.escape(name) + r'\b'
                expanded_text = re.sub(pattern, replacement, expanded_text)
        
        return expanded_text
    
    processed_lines = []
    for line in final_lines:
        if line.strip().startswith('#'):
            continue
        modified_line = expand_macros_in_text(line)
        processed_lines.append(modified_line)
    
    return '\n'.join(processed_lines)


def c4vm_c_preprocess(src: str,src_path_root: str):
    src = c4vm_c_preprocess_remove_comment(src)
    src = c4vm_c_preprocess_include(src,src_path_root)
    src = c4vm_c_preprocess_defines(src)
    return src

def c4vm_c_compile(src_entry):
    if not os.path.isfile(src_entry):
        print("[ERRO] c4vm_c_compile : {0} does not exist".format(src_entry))
        sys.exit()
    src_path_root = os.path.dirname(src_entry)
    try:
        with open(src_entry,'r',encoding='utf-8') as f:
            src = f.read()
    except Exception as e:
        print(e)
        print("[ERRO] c4vm_c_compile : failed when opening {0}".format(src_entry))
        sys.exit(1)
    src = c4vm_c_preprocess(src,src_path_root)
    ... # TODO

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
    src_entry       = './c4vm.c'
    program_bytes   = c4vm_c_compile(src_entry)
    # packed_bytes    = c4vm_pack(program_bytes,space=1*1024*1024)
    # pack_to_file(packed_bytes,"./c4vm.image")