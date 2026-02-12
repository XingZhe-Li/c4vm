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
    # TODO
    ...

def c4vm_c_preprocess(src: str,src_path_root: str):
    src = c4vm_c_preprocess_remove_comment(src)
    src = c4vm_c_preprocess_include(src,src_path_root)
    src = c4vm_c_preprocess_defines(src)

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
    src_entry       = './test.c'
    program_bytes   = c4vm_c_compile(src_entry)
    # packed_bytes    = c4vm_pack(program_bytes,space=1*1024*1024)
    # pack_to_file(packed_bytes,"./c4vm.image")