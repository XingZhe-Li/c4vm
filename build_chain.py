import contextlib
import io
import os
import re
import struct
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import codegen
import lexer
import parser
import preprocess

TEMPLATE = os.path.join(ROOT, "c4vmatrix.c")
PUZZLE   = os.path.join(ROOT, "puzzle.c")
LV1      = os.path.join(ROOT, "lv1.c")
LV2      = os.path.join(ROOT, "lv2.c")

LV1_STACK_QWORDS = 512
LV2_STACK_QWORDS = 4096

DECL_RE = re.compile(r"long long\s+code\s*\[[^\]]*\]\s*=\s*\{[^}]*\}\s*;", re.S)


def compile_to_qwords(source_path):
    with open(source_path, "r", encoding="utf-8") as f:
        src = f.read()

    tokens = lexer.tokenize(src)
    tokens = preprocess.entry(tokens, ROOT)
    ast = parser.parse(tokens)

    sink = io.StringIO()
    with contextlib.redirect_stdout(sink):
        raw = codegen.entry(ast)

    return list(struct.unpack("<%dq" % (len(raw) // 8), raw))


def embed_image(template_path, image_qwords, stack_qwords, out_path):
    with open(template_path, "r", encoding="utf-8") as f:
        host = f.read()

    values = list(image_qwords) + [0] * stack_qwords
    declaration = "long long code[%d] = {%s};" % (
        len(values), ",".join(str(v) for v in values)
    )

    host, count = DECL_RE.subn(declaration, host, count=1)
    if count != 1:
        raise SystemExit("code[] declaration not found in %s" % template_path)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(host)

    print("%-8s image=%d qwords  stack=%d qwords  total=%d qwords" % (
        os.path.basename(out_path), len(image_qwords), stack_qwords, len(values)
    ))


def main():
    puzzle_qwords = compile_to_qwords(PUZZLE)
    embed_image(TEMPLATE, puzzle_qwords, LV1_STACK_QWORDS, LV1)

    lv1_qwords = compile_to_qwords(LV1)
    embed_image(TEMPLATE, lv1_qwords, LV2_STACK_QWORDS, LV2)


if __name__ == "__main__":
    main()
