"""验证数值转换的各个边界，并与宿主 C 的浮点比较结果进行对照。"""

import os
import subprocess

import compiler
import codegen
import lexer
import parser
import preprocess
from tests.vm_support import ROOT, VMTestCase


class NumericTests(VMTestCase):
    PROGRAMS = [
        ("assignment", 'int main(){double x=1;int y=-2.9;x=3;printf("%d %d",(int)x,y);return 0;}', "3 -2"),
        ("assignment_result", 'int main(){double x,r;int y;r=(x=y=2.75);printf("%d %d %d",(int)(x*10),y,(int)(r*10));return 0;}', "20 2 20"),
        ("aggregate_initializers", 'struct S{double x;int y;};int main(){double a[2]={1,2};int b[2]={2.9,-3.9};struct S s={4,-5.5};printf("%d %d %d %d %d",(int)a[1],b[0],b[1],(int)s.x,s.y);return 0;}', "2 2 -3 4 -5"),
        ("indirect_assignment", 'struct S{double x;};int main(){double a[2];double *p=a;struct S s;p[0]=3;*(p+1)=4;s.x=5;printf("%d",(int)(a[0]+a[1]+s.x));return 0;}', "12"),
        ("compound_assignment", 'int main(){int a[2]={3,7};int i=0;double d=3;a[i++]+=2.75;d*=2;printf("%d %d %d",i,a[0],(int)(d*10));return 0;}', "1 5 60"),
        ("parameter_and_return", 'double f(double x,int y){return x+y;}int g(double x){return x;}int main(){printf("%d %d",(int)(f(1,2.9)*10),g(-3.9));return 0;}', "30 -3"),
        ("nested_returns", 'double f(int x){for(int i=0;i<1;i++){if(x)return x;}return 0;}int g(double x){while(x){if(x<0)return x;break;}return x;}int main(){printf("%d %d",(int)(f(3)*10),g(-2.9));return 0;}', "30 -2"),
        ("function_pointers", 'int f(double x){return x;}double g(int x){return x;}int main(){int(*p)(double)=f;double(*q)(int)=g;printf("%d %d %d",(*p)(2),(0?p:p)(3.9),(int)(q(4.9)*10));return 0;}', "2 3 40"),
        ("call_result_type", 'double f(int x){return x;}int main(){printf("%d",f(3)+0.5==3.5);return 0;}', "1"),
        ("byte_and_enum", 'enum E{A=3};double f(unsigned char x){return x;}int main(){unsigned char c=255.9;signed char s=-2.9;double d=A;printf("%d %d %d %d",c,s,f(255.9)==255.0,d==3.0);return 0;}', "255 -2 1 1"),
        ("unsigned64", 'unsigned long long f(double x){return x;}double g(unsigned long long x){return x;}int main(){unsigned long long u=10000000000000000000.0;double d=u;double e=u+0;printf("%d %d %d %d",d==10000000000000000000.0,g(f(d))==d,(u+0.0)>0.0,e==d);return 0;}', "1 1 1 1"),
        ("arithmetic", 'int main(){double x=1+2.5;double y=4-1.5;double z=2*1.5;double q=3/2.0;printf("%d %d %d %d",x==3.5,y==2.5,z==3.0,q==1.5);return 0;}', "1 1 1 1"),
        ("negative_zero", 'int main(){double z=-0.0;printf("%d %d %d %d",z==0.0,1.0/z<0.0,!z,!0.5);return 0;}', "1 1 1 0"),
        ("truth_and_short_circuit", 'int main(){double z=-0.0;int n=0;z&&(n=1);0.5||(n=2);printf("%d %d %d %d",n,z&&0.5,z||0.5,0.5&&2.5);return 0;}', "0 0 1 1"),
        ("floating_conditions", 'int main(){int n=0;double x=2;while(x){n++;x-=1;}for(double y=2;y;y-=1)n++;do{n++;}while(-0.0);if(-0.0)n=99;else n++;printf("%d",-0.0?99:n);return 0;}', "6"),
        ("single_evaluation", 'double f(double x){return x;}int main(){int n=0;double y=f(n++);printf("%d %d",(int)y,n);return 0;}', "0 1"),
        ("builtin_arguments", 'int main(){char *p=malloc(4.9);memset(p,65.9,3.9);p[3]=0;printf("%s",p);free(p);return 0;}', "AAA"),
        ("constant_initializers", 'double x=(double)3;int y=(int)-2.9;int same=1==1.0;int less=-2.0 < -1.0;unsigned long long u=(unsigned long long)10000000000000000000.0;double a[2]={1,2};int main(){printf("%d %d %d %d %d",(int)x,y,same,less,u==10000000000000000000.0&&a[1]==2.0);return 0;}', "3 -2 1 1 1"),
        ("scalar_braces", 'int main(){double x={1};int y={-2.9};printf("%d %d",x==1.0,y);return 0;}', "1 -2"),
        ("global_aggregate", 'struct S{double x;int y;};struct S s={3,-2.9};double a[2]={1,2};int b[2]={1.9,-2.9};int main(){printf("%d %d %d %d",s.x==3.0,s.y,a[1]==2.0,b[1]);return 0;}', "1 -2 1 -2"),
        ("precision_rounding", 'int same=9007199254740993==9007199254740992.0;double chosen=1?2:2.5;int main(){long long x=9007199254740993;printf("%d %d %d",x==9007199254740992.0,same,chosen==2.0);return 0;}', "1 1 1"),
        ("nan_truth", 'int main(){double z=0.0,n=z/z;int x=0;if(n)x++;printf("%d %d %d %d",x,!n,n&&0.5,n||0.0);return 0;}', "1 0 1 1"),
        ("callback_parameter", 'double f(double x){return x+0.5;}double apply(double(*fn)(double),int x){return fn(x);}int main(){printf("%d",apply(f,2.9)==2.5);return 0;}', "1"),
        ("constant_arithmetic", 'double a=3/2.0;int b=1+2.5;double c=(double)3/2;int branch=-0.0?99:((2.0<=2)&&(2>=2.0)&&(1.0!=2)&&(3.0>2));int main(){printf("%d %d %d %d",a==1.5,b,c==1.5,branch);return 0;}', "1 3 1 1"),
    ]

    def test_comparisons_against_native_c(self):
        # 全部六种比较同时覆盖负数、正负零、无穷大、NaN，以及两侧混合整数。
        source = '''#include <stdio.h>
int main(void) {
    double zero=0.0, inf=1.0/zero, nan=zero/zero;
    double a[9]={-inf,-3.5,-1,-0.0,0.0,2,2.5,inf,nan};
    for(int i=0;i<9;i++) {
        for(int j=0;j<9;j++) {
            printf("%d%d%d%d%d",a[i]==a[j],a[i]!=a[j],a[i]<a[j],a[i]>a[j],a[i]<=a[j]);
            printf("%d",a[i]>=a[j]);
        }
        for(int k=-2;k<3;k++) {
            printf("%d%d%d%d%d",a[i]==k,a[i]!=k,a[i]<k,k>a[i],k<=a[i]);
            printf("%d",k>=a[i]);
        }
    }
    return 0;
}'''
        path = self.work / "native-comparisons.c"
        path.write_text(source, encoding="utf-8")
        executable = path.with_suffix(".exe" if os.name == "nt" else "")
        subprocess.run([*self.cc, "-std=c11", "-O2", *self.cflags, str(path), "-o", str(executable)],
                       capture_output=True, text=True, check=True)
        native = subprocess.run([str(executable)], capture_output=True, text=True, timeout=3)
        self.assertEqual(native.returncode, 0, native.stderr)
        self.assertEqual(len(native.stdout), 756)
        self.assert_output(source, native.stdout)

    def test_matrix_in_matrix_numeric_operations(self):
        from tools import build_matrix_in_matrix as matrix
        source = self.work / "numeric-inner.c"
        source.write_text('double f(double x){return x+0.5;}int main(){double x=f(2);int y=-2.9;double z=-0.0;double zero=0.0,nan=zero/zero;unsigned long long u=10000000000000000000.0;printf("%d %d %d %d %d",x==2.5,y,-2.0 < -1.0,1.0/z < 0.0,nan!=nan && u==10000000000000000000.0);return 0;}', encoding="utf-8")
        _, outer = matrix.build_matrix_in_matrix(source, self.work / "numeric-matrix")
        executable = outer.with_suffix(".exe" if os.name == "nt" else "")
        compiled = subprocess.run([*self.cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Wpedantic", "-Werror",
                                   *self.cflags, str(outer), "-o", str(executable)], capture_output=True, text=True)
        self.assertEqual(compiled.returncode, 0, compiled.stderr)
        result = subprocess.run([str(executable)], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.stdout, "1 -2 1 1 1", result.stderr)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_opcode_tables_agree(self):
        source = '#define C4VM_EMBEDDED\n' + (ROOT / "c4vm.c").read_text(encoding="utf-8") + '\nint main(void){return 0;}'
        ast = parser.parse(preprocess.entry(lexer.tokenize(source), str(ROOT)))
        symbols = ast.metas[0]
        for name, number in codegen.opcode.items():
            self.assertEqual(symbols.get((name,))[1].value, number, name)
        self.assertEqual(codegen.opcode["SCNF"], 56)  # 保持原有镜像的指令编号。

    def test_invalid_numeric_conversions(self):
        for source in ['int main(){double x=(int*)0;return 0;}',
                       'int main(){int *p=2.5;return 0;}',
                       'double f(int *p){return p;}int main(){return 0;}',
                       'int f(double x){return x;}int main(){return f();}']:
            with self.subTest(source=source):
                path = self.work / "invalid-numeric.c"
                path.write_text(source, encoding="utf-8")
                with self.assertRaises(ValueError):
                    compiler.compile_raw(path)

    def test_integer_exit_status_from_float(self):
        self.assertEqual(self.run_source('int main(){return 2.9;}').returncode, 2)
        self.assertEqual(self.run_source('int main(){exit(7.9);}').returncode, 7)


def numeric_test(source, expected):
    def test(self):
        self.assert_output(source, expected)
    return test


for name, source, expected in NumericTests.PROGRAMS:
    setattr(NumericTests, "test_numeric_" + name, numeric_test(source, expected))
