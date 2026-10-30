"""覆盖词法、宏展开/条件包含及镜像打包的正常输入和错误边界。"""

import unittest
from pathlib import Path

import lexer
import packer
import preprocess
from tests import temporary_directory


class LexerTests(unittest.TestCase):
    def values(self, source):
        return [(token.tktype, token.value) for token in lexer.tokenize(source)]

    def test_string_at_start_and_concatenation(self):
        self.assertEqual(self.values('"a" /* gap */\n "b"'), [("string", "ab")])

    def test_number_spellings(self):
        self.assertEqual(
            self.values("0xff 0XAB 077 .5 1.5e+2 0E-2 2E3"),
            [("integer", 255), ("integer", 171), ("integer", 63),
             ("float", .5), ("float", 150.), ("float", 0.), ("float", 2000.)],
        )

    def test_escapes(self):
        self.assertEqual(self.values(r'''"\x41\101\n\t\\\"" '\0' '''),
                         [("string", 'AA\n\t\\"'), ("integer", 0)])

    def test_bad_input_has_line_number(self):
        for source in ['\n"unfinished', "\n'", "\n/* unfinished", "\n@", "\n0x", "\n09"]:
            with self.subTest(source=source), self.assertRaisesRegex(SyntaxError, "line 2"):
                lexer.tokenize(source)

    def test_comment_line_numbers(self):
        self.assertEqual(lexer.tokenize("/* a\nb */\nx")[0].line, 3)


class PreprocessorTests(unittest.TestCase):
    def expand(self, source, cwd="."):
        return [token.value for token in preprocess.entry(lexer.tokenize(source), cwd)]

    def test_nested_disabled_branch(self):
        self.assertEqual(self.expand("#ifdef NO\n#ifndef YES\nhidden\n#endif\n#endif\nvisible"),
                         ["visible"])

    def test_disabled_defines_and_includes_have_no_effect(self):
        self.assertEqual(self.expand('#ifdef NO\n#define X 1\n#include "missing.h"\n#endif\nX'), ["X"])

    def test_empty_macro(self):
        self.assertEqual(self.expand("#define EMPTY\nEMPTY x"), ["x"])

    def test_recursive_expansion_and_self_reference(self):
        self.assertEqual(self.expand("#define A B\n#define B 42\nA"), [42])
        self.assertEqual(self.expand("#define A B\n#define B A\nA"), ["A"])

    def test_undef_unknown_is_allowed(self):
        self.assertEqual(self.expand("#undef UNKNOWN\nx"), ["x"])

    def test_unbalanced_conditionals(self):
        for source in ["#else", "#endif", "#ifdef X\nx", "#ifdef X\n#else\n#else\n#endif"]:
            with self.subTest(source=source), self.assertRaises(SyntaxError):
                self.expand(source)

    def test_missing_include_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            self.expand('#include "nonexistent-header.h"')

    def test_nested_relative_include(self):
        with temporary_directory() as directory:
            root = Path(directory)
            (root / "sub").mkdir()
            (root / "sub" / "a.h").write_text('#include "b.h"\nA', encoding="utf-8")
            (root / "sub" / "b.h").write_text('#define A 23', encoding="utf-8")
            self.assertEqual(self.expand('#include "sub/a.h"', directory), [23])

    def test_include_guard_and_cycle(self):
        with temporary_directory() as directory:
            header = Path(directory) / "a.h"
            header.write_text('#ifndef GUARD\n#define GUARD\n#include "a.h"\nx\n#endif', encoding="utf-8")
            self.assertEqual(self.expand('#include "a.h"\n#include "a.h"', directory), ["x"])
            header.write_text('#include "a.h"', encoding="utf-8")
            with self.assertRaisesRegex(SyntaxError, "include nesting"):
                self.expand('#include "a.h"', directory)


class PackerTests(unittest.TestCase):
    def test_image_header(self):
        raw = bytes(64)
        self.assertEqual(packer.packer(raw), (128).to_bytes(8, "little") + raw)
        self.assertEqual(packer.packer(raw, ratio=None, stackspace=64)[:8], (128).to_bytes(8, "little"))
        self.assertEqual(packer.qword_array(b"\xff" * 8), [-1])

    def test_invalid_sizes(self):
        for kwargs in [{"ratio": .5}, {"ratio": None}, {"ratio": None, "fixspace": 8},
                       {"ratio": None, "stackspace": -1}]:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                packer.packer(bytes(16), **kwargs)

    def test_alignment(self):
        self.assertEqual(int.from_bytes(packer.packer(bytes(8), ratio=None, stackspace=65)[:8], "little"), 80)
        with self.assertRaises(ValueError):
            packer.qword_array(bytes(3))


if __name__ == "__main__":
    unittest.main()
