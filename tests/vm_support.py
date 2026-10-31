"""编译执行测试的公共工具：从当前源码构建 VM，并将临时文件集中在 build/。"""

import contextlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import uuid
import unittest

import compiler
from tests import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


class VMTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = temporary_directory()
        cls.work = Path(cls.directory.name)
        cls.vm = cls.work / ("c4vm.exe" if os.name == "nt" else "c4vm")
        compiler_command = os.environ.get("CC", "gcc")
        cc = [compiler_command] if Path(compiler_command).is_file() else shlex.split(compiler_command)
        cls.cc = cc
        cls.cflags = shlex.split(os.environ.get("CFLAGS", ""))
        if not shutil.which(cc[0]):
            raise RuntimeError("Tests require a C compiler; set CC or install GCC.")
        subprocess.run([*cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic",
                        *cls.cflags, str(ROOT / "c4vm.c"), "-o", str(cls.vm)], check=True, capture_output=True, text=True)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_source(self, source, args=(), stdin=""):
        path = self.work / f"{uuid.uuid4().hex}.c"
        image = path.with_suffix(".vm")
        path.write_text(source, encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            compiler.compile(str(path), str(image))
        return subprocess.run([str(self.vm), str(image), *args], input=stdin, capture_output=True,
                              text=True, timeout=3)

    def assert_output(self, source, expected):
        result = self.run_source(source)
        self.assertEqual(result.stdout, expected, result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)
