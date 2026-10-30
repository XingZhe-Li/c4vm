"""将 C 子集源文本转换为保留行号的 Token，拒绝非法字符和未闭合字面量。

注释/空白不进入输出，行首预处理指令整体保留为 macro，供 preprocess 处理。
此处识别的数值及转义语法只是项目支持的子集。
"""

import re
from common import Token

NUMBER = re.compile(r"(?:0[xX][0-9a-fA-F]+|(?:\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?|\d+[eE][+-]?\d+|\d+)")
IDENTIFIER = re.compile(r"[a-zA-Z_][a-zA-Z_0-9]*")
# 较长运算符必须先匹配，例如 >>= 不能拆成 >> 与 =。
OPERATORS = re.compile(r">>=|<<=|\+\+|--|->|&&|\|\||<<|>>|[+*/%&|^!<>=-]=|[+*/%&|^!<>=~()\[\]{},;.?:-]")
ESCAPES = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
           "v": "\v", "\\": "\\", "'": "'", '"': '"', "?": "?"}


def tokenize(src: str) -> list[Token]:
    tokens = []
    idx, line = 0, 1
    line_start = True

    def error(message, at_line=None):
        raise SyntaxError(f"line {line if at_line is None else at_line}: {message}")

    while idx < len(src):
        char = src[idx]
        if char.isspace():
            if char == "\n":
                line += 1
                line_start = True
            idx += 1
            continue
        if src.startswith("//", idx):
            end = src.find("\n", idx)
            idx = len(src) if end == -1 else end
            continue
        if src.startswith("/*", idx):
            end = src.find("*/", idx + 2)
            if end == -1:
                error("unterminated comment")
            newlines = src.count("\n", idx, end + 2)
            line += newlines
            if newlines:
                line_start = True
            idx = end + 2
            continue
        if char == "#":
            if not line_start:
                error("preprocessor directive must start a line")
            end = src.find("\n", idx)
            end = len(src) if end == -1 else end
            tokens.append(Token("macro", src[idx + 1:end], line))
            idx = end
            line_start = False
            continue
        line_start = False
        if char in "\"'":
            quote, start_line = char, line
            idx += 1
            buf = ""
            while idx < len(src) and src[idx] != quote:
                char = src[idx]
                if char == "\n":
                    error("newline in literal", start_line)
                if char != "\\":
                    buf += char
                    idx += 1
                    continue
                idx += 1
                if idx == len(src):
                    error("unterminated escape", start_line)
                char = src[idx]
                if char in ESCAPES:
                    buf += ESCAPES[char]
                    idx += 1
                elif char in "01234567":
                    match = re.match(r"[0-7]{1,3}", src[idx:])
                    buf += chr(int(match[0], 8))
                    idx += len(match[0])
                elif char == "x":
                    match = re.match(r"[0-9a-fA-F]+", src[idx + 1:])
                    if not match:
                        error("hex escape requires digits", start_line)
                    value = int(match[0], 16)
                    if value > 255:
                        error("hex escape exceeds one byte", start_line)
                    buf += chr(value)
                    idx += 1 + len(match[0])
                else:
                    error(f"unknown escape \\{char}", start_line)
            if idx == len(src):
                error("unterminated literal", start_line)
            idx += 1
            if quote == "'":
                if len(buf) != 1:
                    error("character literal requires one character", start_line)
                tokens.append(Token("integer", ord(buf), start_line))
            elif tokens and tokens[-1].tktype == "string":
                tokens[-1].value += buf
            else:
                tokens.append(Token("string", buf, start_line))
        elif char.isdigit() or (char == "." and idx + 1 < len(src) and src[idx + 1].isdigit()):
            match = NUMBER.match(src, idx)
            spelling = match[0]
            idx = match.end()
            if idx < len(src) and (src[idx].isalnum() or src[idx] == "_"):
                error("invalid numeric literal")
            if spelling.lower().startswith("0x"):
                kind, value = "integer", int(spelling, 16)
            elif any(c in spelling for c in ".eE"):
                kind, value = "float", float(spelling)
            else:
                try:
                    kind, value = "integer", int(spelling, 8 if spelling.startswith("0") else 10)
                except ValueError:
                    error("invalid octal literal")
            tokens.append(Token(kind, value, line))
        elif match := IDENTIFIER.match(src, idx):
            tokens.append(Token("identifier", match[0], line))
            idx = match.end()
        elif match := OPERATORS.match(src, idx):
            tokens.append(Token("operator", match[0], line))
            idx = match.end()
        else:
            error(f"unexpected character {char!r}")
    return tokens
