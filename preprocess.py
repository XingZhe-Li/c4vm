"""展开对象宏、相对路径头文件及 ifdef/ifndef 条件组，输出解析器使用的 Token。

包含的文件共享宏定义，各自维护条件栈。尖括号标准头文件由 VM 内置函数替代；
本模块不实现完整的标准 C 预处理器。
"""

import os
import re
import lexer
from common import Token


def entry(tokens: list[Token], cwd: str) -> list[Token]:
    return preprocess(tokens, {}, [], cwd)


def preprocess(tokens, define_table, including_stack, cwd, depth=0):
    if depth > 100:
        raise SyntaxError("include nesting exceeds 100 files (possible include cycle)")
    output = []
    # Each file owns its conditional groups; definitions are shared by includes.
    groups = []

    def expand(token, disabled=frozenset()):
        # 一条展开路径中禁用已展开的名称，允许 A -> B，同时阻止 A -> B -> A 循环。
        name = token.value
        if token.tktype == "identifier" and name in define_table and name not in disabled:
            for replacement in define_table[name]:
                yield from expand(Token(replacement.tktype, replacement.value, token.line), disabled | {name})
        else:
            yield token

    for token in tokens:
        active = all(group[0] for group in groups)
        if token.tktype != "macro":
            if active:
                output.extend(expand(token))
            continue
        directive = token.value.strip()

        def error(message):
            raise SyntaxError(f"line {token.line}: {message}")

        if match := re.fullmatch(r"(ifdef|ifndef)\s+([a-zA-Z_]\w*)", directive):
            condition = match[2] in define_table
            groups.append([condition if match[1] == "ifdef" else not condition, False])
        elif directive == "else":
            if not groups or groups[-1][1]:
                error("unmatched or duplicate #else")
            groups[-1] = [not groups[-1][0], True]
        elif directive == "endif":
            if not groups:
                error("unmatched #endif")
            groups.pop()
        elif not active:
            continue
        elif match := re.fullmatch(r'include\s+(<[^>]+>|"[^"]+")', directive):
            target = match[1]
            if target.startswith("<"):
                continue  # Host library functions are supplied by VM builtins.
            path = os.path.join(cwd, target[1:-1])
            with open(path, encoding="utf-8") as source:
                included = lexer.tokenize(source.read())
            output.extend(preprocess(included, define_table, [], os.path.dirname(path), depth + 1))
        elif match := re.fullmatch(r"define\s+([a-zA-Z_]\w*)(.*)", directive):
            if match[2].startswith("("):
                error("function-like macros are not supported")
            define_table[match[1]] = lexer.tokenize(match[2].strip())
        elif match := re.fullmatch(r"undef\s+([a-zA-Z_]\w*)", directive):
            define_table.pop(match[1], None)
        else:
            error(f"unsupported preprocessor directive #{directive}")
    if groups:
        raise SyntaxError("unterminated #ifdef/#ifndef group")
    return output
