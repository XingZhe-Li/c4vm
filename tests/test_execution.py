"""从当前 C 源码构建解释器，验证编译结果、宿主接口和 matrix-in-matrix 执行。"""

import contextlib
import io
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import uuid
import unittest

import compiler
from tests import temporary_directory

ROOT = Path(__file__).resolve().parents[1]


class ExecutionTests(unittest.TestCase):
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

    PROGRAMS = [
            ("arithmetic", 'int main(){printf("%d", (2+3)*4-7/2+8%3); return 0;}', "19"),
            ("recursion", 'int f(int n){if(n<2)return 1; return n*f(n-1);} int main(){printf("%d", f(6));return 0;}', "720"),
            ("scope", 'int main(){int x=2; {int x=5; printf("%d ",x);} printf("%d",x);return 0;}', "5 2"),
            ("while", 'int main(){int i=0,s=0;while(i<6){i++;if(i==2)continue;if(i==5)break;s+=i;}printf("%d",s);return 0;}', "8"),
            ("for_decl", 'int main(){int s=0;for(int i=0;i<5;i++){s+=i;}printf("%d",s);return 0;}', "10"),
            ("for_expr", 'int main(){int i=0,s=0;for(i=0;i<5;i++){s+=i;}printf("%d",s);return 0;}', "10"),
            ("for_empty", 'int main(){int i=0;for(;;){i++;if(i==4)break;}printf("%d",i);return 0;}', "4"),
            ("empty_statements", 'int main(){if(0);else;while(0);for(int i=0;i<0;i++);return 0;}', ""),
            ("do_continue", 'int main(){int i=0;do{i++;if(i<3)continue;break;}while(0);printf("%d",i);return 0;}', "1"),
            ("logic", 'int main(){int x=0;0&&(x=1);1||(x=2);printf("%d %d %d",x,2&&7,2||7);return 0;}', "0 1 1"),
            ("assignment_chain", 'int main(){int a=0,b=0;a=b=7;printf("%d %d",a,b);return 0;}', "7 7"),
            ("ternary", 'int main(){printf("%d",1?0:1?2:3);return 0;}', "0"),
            ("global_array", 'int a[3]={11,22,33};int main(){int *p=a;printf("%d",p[1]);return 0;}', "22"),
            ("local_array", 'int main(){int a[3]={11,22,33};printf("%d",a[2]);return 0;}', "33"),
            ("matrix", 'int main(){int a[2][2]={{1,2},{3,4}};int *p=a[1];printf("%d %d",a[1][1],p[0]);return 0;}', "4 3"),
            ("char_deref", 'int main(){char a[3]={65,66,0};char *p=a;printf("%d",*p);return 0;}', "65"),
            ("unsigned_char_size", 'int main(){unsigned char a[3];printf("%d",sizeof(a));return 0;}', "3"),
            ("function_pointer", 'int f(int a){return a+1;}int main(){int (*p)(int)=f;printf("%d",p(5));return 0;}', "6"),
            ("typed_call", 'int f(){return 3;}int main(){printf("%d",f()+2);return 0;}', "5"),
            ("sizeof_expression", 'int main(){int x=1;printf("%d %d",sizeof(x++),x);return 0;}', "8 1"),
            ("struct", 'struct S{char x;int y;};int main(){struct S a={65,9};struct S *p=&a;printf("%d %d",a.x,p->y);return 0;}', "65 9"),
            ("float_cast", 'int main(){double x=2.5;printf("%d",(int)(x*2+1));return 0;}', "6"),
            ("heap", 'int main(){char *p=malloc(16);memset(p,0,16);p[0]=65;printf("%s",p);free(p);return 0;}', "A"),
            ("strstr_null", 'int main(){printf("%d",strstr("abc","z")==0);return 0;}', "1"),
            ("memcpy_return", 'int main(){char a[4],b[4]={65,66,0,0};char *p=memcpy(a,b,4);printf("%d %s",p==a,p);return 0;}', "1 AB"),
            ("printf_percent", 'int main(){printf("%% %s", "ok");return 0;}', "% ok"),
            ("printf_literal_percent", 'int main(){printf("%% hello %s", "ok");return 0;}', "% hello ok"),
            ("pointer_step", 'int main(){int a[3]={11,22,33};int *p=a;int *q=p++;printf("%d %d ",*q,*p);++p;printf("%d ",*p);--p;p--;printf("%d",*p);return 0;}', "11 22 33 11"),
            ("pointer_difference", 'int main(){int a[4];int *p=&a[3];int *q=&a[1];printf("%d",p-q);return 0;}', "2"),
            ("array_arithmetic", 'int main(){int a[3]={11,22,33};printf("%d %d",*(a+1),*(2+a));return 0;}', "22 33"),
            ("unsigned_byte", 'int main(){unsigned char a[2]={255,128};printf("%d %d",a[0],*a);return 0;}', "255 255"),
            ("signed_byte", 'int main(){signed char c=65;printf("%d %d",sizeof(c),c);return 0;}', "1 65"),
            ("compound_side_effect", 'int main(){int a[3]={10,20,30};int i=0;a[i++]+=5;printf("%d %d %d",i,a[0],a[1]);return 0;}', "1 15 20"),
            ("negative_global", 'int x=-7;int main(){printf("%d",x);return 0;}', "-7"),
            ("constant_global", 'int x=2+3*4;int main(){printf("%d",x);return 0;}', "14"),
            ("negative_float", 'int main(){double x=2.5;printf("%d",(int)(-x*2));return 0;}', "-5"),
            ("sizeof_type", 'int main(void){printf("%d %d %d",sizeof(int),sizeof(char),sizeof(int*));return 0;}', "8 1 8"),
            ("ptr_attr_expression", 'struct S{int x;};int main(){struct S a={19};printf("%d",(&a)->x);return 0;}', "19"),
            ("global_function_pointer", 'int f(int n){return n+2;}int (*p)(int)=f;int main(){printf("%d",p(3));return 0;}', "5"),
            ("ternary_float", 'int main(){double x=1?2:2.5;printf("%d",(int)(x*3));return 0;}', "6"),
            ("designated_initializer", 'int a[4]={[2]=9};int main(){printf("%d %d",a[0],a[2]);return 0;}', "0 9"),
            ("nested_loops", 'int main(){int s=0;for(int i=0;i<3;i++){for(int j=0;j<4;j++){if(j==1)continue;if(j==3)break;s++;}}printf("%d",s);return 0;}', "6"),
            ("string_builtins", 'int main(){char a[16]={65,0};strcat(a,"BC");printf("%s %d %d",a,strlen(a),strcmp(a,"ABC"));return 0;}', "ABC 3 0"),
            ("bitwise", 'int main(){printf("%d %d %d",(5|2)^1,(12&7)<<1,~0);return 0;}', "6 8 -1"),
            ("implicit_main_return", 'int main(){printf("ok");}', "ok"),
            ("partial_local_init", 'int f(int n){int a[2]={[1]=n};return a[0];}int main(){printf("%d %d",f(7),f(9));return 0;}', "0 0"),
            ("scalar_braces", 'int x={3};int main(){int y={4};printf("%d",x+y);return 0;}', "7"),
            ("array_parameter", 'int f(int a[3]){return a[1];}int main(){int a[3]={1,2,3};printf("%d",f(a));return 0;}', "2"),
            ("union", 'union U{char c;int x;};int main(){union U a;a.x=65;printf("%d %d",a.c,a.x);return 0;}', "65 65"),
        ]
    def test_main_args(self):
        result = self.run_source('int main(int argc,char **argv){printf("%d %s %d",argc,argv[1],argv[argc]==0);return 0;}', ["hello"])
        self.assertEqual(result.stdout, "2 hello 1")

    def test_scanf(self):
        result = self.run_source('int main(){long long x=0;scanf("%lld",&x);printf("%lld",x);return 0;}', stdin="-123")
        self.assertEqual(result.stdout, "-123")
        self.assertEqual(result.returncode, 0)

    def test_matrix_in_matrix(self):
        from tools import build_matrix_in_matrix as matrix
        source = self.work / "inner.c"
        source.write_text('int f(int x){return x+2;}int main(){int(*p)(int)=f;char*s=malloc(4);memset(s,0,4);s[0]=65;printf("%s %d",s,p(5));free(s);return 0;}', encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            words = matrix.compile_to_qwords(source)
            for level, stack in [(1, 512), (2, 4096)]:
                host = self.work / f"level{level}.c"
                executable = self.work / (f"level{level}.exe" if os.name == "nt" else f"level{level}")
                matrix.write_embedded_program(words, stack, host)
                subprocess.run([*self.cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                                *self.cflags, str(host), "-o", str(executable)], capture_output=True, text=True, check=True)
                result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=3)
                self.assertEqual(result.stdout, "A 7", result.stderr)
                self.assertEqual(result.returncode, 0, result.stderr)
                if level == 1:
                    words = matrix.compile_to_qwords(host)

    def test_matrix_tool_cli_from_another_directory(self):
        # 默认示例相对于仓库定位，用户给出的输出目录则相对于调用者定位。
        directory = self.work / "matrix output"
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_matrix_in_matrix.py"),
                                 "--output-dir", directory.name], cwd=self.work,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((directory / "matrix.c").is_file())
        executable = directory / ("outer.exe" if os.name == "nt" else "outer")
        subprocess.run([*self.cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                        *self.cflags, str(directory / "matrix_in_matrix.c"), "-o", str(executable)],
                       capture_output=True, text=True, check=True)
        executed = subprocess.run([str(executable)], capture_output=True, text=True, timeout=3)
        self.assertEqual(executed.stdout, "Hello World!!!", executed.stderr)
        self.assertEqual(executed.returncode, 0, executed.stderr)

    def test_matrix_tool_errors(self):
        from tools import build_matrix_in_matrix as matrix
        for stack in [-1, 0, 3]:
            with self.subTest(stack=stack), self.assertRaisesRegex(ValueError, "stack"):
                matrix.write_embedded_program([0], stack, self.work / "invalid-wrapper.c")
        directory = self.work / "preserved"
        directory.mkdir()
        source = directory / "matrix.c"
        original = "int main(void){return 0;}"
        source.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "input source"):
            matrix.build_matrix_in_matrix(source, directory)
        self.assertEqual(source.read_text(encoding="utf-8"), original)
        result = subprocess.run([sys.executable, str(ROOT / "tools" / "build_matrix_in_matrix.py"),
                                 str(self.work / "nonexistent.c"), "--output-dir", str(directory)],
                                capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)

    def test_exit_status(self):
        self.assertEqual(self.run_source("int main(){return 7;}").returncode, 7)
        self.assertEqual(self.run_source("int main(){exit(9);}").returncode, 9)

    def test_invalid_images(self):
        for data in [b"", b"short", bytes(8), (-8).to_bytes(8,"little",signed=True),
                     (1024).to_bytes(8,"little") + bytes(4),
                     (16).to_bytes(8,"little") + bytes(32)]:
            with self.subTest(data=data):
                path = self.work / "bad-image.vm"
                path.write_bytes(data)
                result = subprocess.run([str(self.vm), str(path)], capture_output=True, text=True, timeout=3)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("image", result.stderr)

    def test_unknown_opcode(self):
        import packer
        path = self.work / "unknown.vm"
        path.write_bytes(packer.packer((999).to_bytes(8,"little") + bytes(8), ratio=None, stackspace=128))
        result = subprocess.run([str(self.vm), str(path)], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 1)
        self.assertIn("unknown instruction", result.stderr)

    def test_source_relative_include(self):
        (self.work / "answer.h").write_text("#define ANSWER 42", encoding="utf-8")
        self.assert_output('#include "answer.h"\nint main(){printf("%d",ANSWER);return 0;}', "42")

    def test_invalid_source_fails_promptly(self):
        for source in ["int main( {", "int main(){ @ }", "int main(){ int x = ; }",
                       "int main(){ int x;", "struct S { int x;", "int main(){break;}",
                       "int main(){1=2;}", "int helper(){return 0;}", "int main(){missing();}",
                       "int main(){printf();}", "int main(){int a[1]={1,2};}",
                       "int main(){for(int i=0;i<1;i++);return i;}"]:
            with self.subTest(source=source):
                path = self.work / "invalid.c"
                path.write_text(source, encoding="utf-8")
                result = subprocess.run([sys.executable, str(ROOT / "compiler.py"), str(path), str(self.work / "bad.vm")],
                                        capture_output=True, text=True, timeout=3)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)


def program_test(source, expected):
    def test(self):
        self.assert_output(source, expected)
    return test


for name, source, expected in ExecutionTests.PROGRAMS:
    setattr(ExecutionTests, "test_program_" + name, program_test(source, expected))


if __name__ == "__main__":
    unittest.main()
