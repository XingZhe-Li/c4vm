"""编译入口：连接词法、预处理、解析和代码生成，并按需写出带容量头的 .vm。

compile_raw 返回供内存加载/嵌套执行使用的原始镜像；compile 写出文件加载格式。
"""

import os
import sys
import lexer
import parser
import codegen
import preprocess
import packer
import argparse

def compile_raw(source_path, verbose=False):
    """编译一个源文件，返回以字节地址定位的原始镜像，不包含文件头和栈。"""
    # read source file to src
    with open(source_path,'r',encoding='utf-8') as f:
        src = f.read()
    
    # tokenize
    tokens = lexer.tokenize(src)

    # preprocess
    cwd = os.path.dirname(os.path.abspath(source_path)) # cwd for #include
    tokens = preprocess.entry(tokens,cwd)

    # parse
    ASTRoot = parser.parse(tokens)

    # codegen
    return codegen.entry(ASTRoot,verbose=verbose)


def compile(source_path,target_path,verbose=False):
    """在原始镜像前添加虚拟容量头，并为宿主入口预留 1 MiB 栈。"""
    raw_image = compile_raw(source_path, verbose=verbose)
    # pack
    packed_image = packer.packer(raw_image,ratio=None,stackspace=1 * 1024 * 1024)

    with open(target_path,'wb') as f:
        f.write(packed_image)
    return packed_image

if __name__ == '__main__':
    cli = argparse.ArgumentParser(description="Compile the c4vm C subset to a VM image")
    cli.add_argument("source", help="C source file")
    cli.add_argument("target", nargs="?", default="out.vm", help="output image (default: out.vm)")
    cli.add_argument("--dump", action="store_true", help="show image words for debugging")
    args = cli.parse_args()
    try:
        compile(args.source, args.target, verbose=args.dump)
    except (OSError, SyntaxError, ValueError, OverflowError) as error:
        print(f"error: {error}", file=sys.stderr)
        sys.exit(1)
