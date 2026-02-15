import os
import sys
import lexer
import common
import parser
import codegen
import preprocess
import packer

def show_help():
    print("compiler.py [source] [target]")
    print("    defaults:                ")
    print("        source = hi.c        ")
    print("        target = out.vm      ")

def source_check(source_path):
    if not os.path.isfile(source_path):
        print("[ERRO] source_path = {0} , not exists".format(source_path))
        sys.exit(1)

def compile(source_path,target_path):
    source_check(source_path)
    
    # read source file to src
    with open(source_path,'r',encoding='utf-8') as f:
        src = f.read()
    
    # tokenize
    tokens = lexer.tokenize(src)

    # preprocess
    cwd = os.path.dirname(__file__) # cwd for #include
    tokens = preprocess.entry(tokens,cwd)

    print([tk.value for tk in tokens])

if __name__ == '__main__':
    source = "hi.c"
    target = "out.vm"

    if len(sys.argv) == 1:
        show_help()
        sys.exit(0)
    elif len(sys.argv) >= 2:
        source = sys.argv[1]
    elif len(sys.argv) >= 3:
        target = sys.argv[2]

    compile(source,target)