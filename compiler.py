import os
import sys
import lexer
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

    # parse
    ASTRoot = parser.parse(tokens)

    # codegen
    raw_image = codegen.entry(ASTRoot)

    print("raw_image:",raw_image)
    # sys.exit(1) # codegen WIP

    # if you wanna make a embed long long array
    # just convert it to qword_array by decommenting code below
    # print(packer.qword_array(raw_image))
    # sys.exit(1) # codegen WIP

    # pack
    packed_image = packer.packer(raw_image,ratio=None,stackspace=1 * 1024 * 1024)

    with open(target_path,'wb') as f:
        f.write(packed_image)
    print("compiled successfully!")

if __name__ == '__main__':
    source = "hi.c"
    target = "out.vm"

    if len(sys.argv) == 1:
        show_help()
        sys.exit(0)
    if len(sys.argv) >= 2:
        source = sys.argv[1]
    if len(sys.argv) >= 3:
        target = sys.argv[2]

    compile(source,target)