c4vm
====

受 c4.c 启发的教学用 C 子集编译器与虚拟机。Python 前端生成栈式 VM
字节码，C 解释器执行。保留原有词法、递归下降解析、AST 和代码生成结构。

快速开始（在仓库根目录执行）
--------------------------------
需要 Python 3.10+、64 位 GCC/MinGW-w64 和可选的 CMake/Ninja。
当前目标是小端、64 位宿主；Windows 使用 MinGW，不支持 MSVC。

    cmake -S . -B build -G Ninja -DCMAKE_C_COMPILER=gcc
    cmake --build build
    python compiler.py hi.c build/hi.vm

Windows PowerShell 运行：

    ./build/c4vm.exe build/hi.vm

Linux 运行：

    ./build/c4vm build/hi.vm

输出 Hello World!!!。也可直接构建解释器：

    gcc -std=c11 -O2 -Wall -Wextra -Wpedantic c4vm.c -o c4vm

compiler.py 的第二个参数默认 out.vm；--dump 输出镜像字内容，便于调试。
错误报告到 stderr，并以非零状态退出。解释器将程序的 return/exit 状态传回宿主。
main 的 argc/argv 包含镜像路径作为 argv[0]，argv[argc] 为 0。

测试与覆盖率
--------------
测试会从当前源码临时构建解释器，无需旧的预编译二进制：

    python -m unittest discover -v

或在 CMake 构建后执行：

    ctest --test-dir build --output-on-failure

覆盖率仅针对 Python 编译链；VM 通过编译、执行和结果断言验证。

    python -m pip install -r requirements-dev.txt
    python -m coverage run -m unittest discover -v
    python -m coverage report
    python -m coverage html

.coveragerc 设置 80% 的行/分支综合覆盖率门槛。GitHub Actions 配置了
Ubuntu/Windows 与 Python 3.10/3.13 组合，并保存 coverage.xml。
本地已验证的结果与问题记录见 docs/AUDIT.txt；远程 CI 需推送后实际执行。

目录与构建链
--------------
    lexer.py / preprocess.py    词法与对象宏、条件编译、相对路径 include
    parser.py / common.py       递归下降解析、符号表与 AST 类型
    codegen.py / packer.py       镜像布局、字节码与加载头
    compiler.py                 CLI 与可调用的 compile(source, target)
    c4vm.c                      唯一解释器实现，含宿主与嵌入入口支持
    tools/build_matrix_in_matrix.py  生成 matrix-in-matrix 包装程序的辅助工具
    tests/                      单元测试、完整编译执行、错误输入与两层嵌套测试
    bench/                      质数筛基准
    docs/AST.txt                原有 AST 节点说明

原有 .exe、.vm 和调试转储 hi.txt 已移出工作树；从源码重建即可，历史仍在 Git。
生成文件统一使用 build/，并由 .gitignore 排除。

matrix-in-matrix 工具默认嵌入 hi.c，也可以指定自己的 C 源文件。
它只生成 C 包装程序，后续原生构建使用 GCC：

    python tools/build_matrix_in_matrix.py hi.c --output-dir build/matrix-in-matrix
    gcc -std=c11 -O2 build/matrix-in-matrix/matrix.c -o build/matrix
    gcc -std=c11 -O2 build/matrix-in-matrix/matrix_in_matrix.c -o build/matrix_in_matrix

输出 matrix.c 与 matrix_in_matrix.c。两者只包含镜像数组、入口函数及对唯一
解释器 c4vm.c 的相对 include，不复制解释器源码。C4VM_EMBEDDED 只关闭宿主
文件加载入口，并调整诊断输出；指令执行逻辑完全共用，因此公共核心须保持在
本项目 C 子集内。源文件开头和关键位置有相应约定注释。
这两层执行已纳入回归测试；工具可从任意工作目录运行。
默认内/外层栈分别为 512/4096 个 8 字节字；较大程序可以通过
--inner-stack-qwords 和 --outer-stack-qwords 调整，至少各预留 4 个字。
生成的包装程序依赖当前仓库中的 c4vm.c，复制到其他机器时须保留 include 关系。
嵌入式入口不传递宿主 argc/argv，示例应使用 main(void) 或不读取入口参数。

基准先比较 native C、Python、VM 的输出，再计时，包含进程启动时间：

    python bench/bench.py --runs 5

支持范围与限制
----------------
c4vm 实现了用于学习编译原理的 C 语言子集。编写程序时，请以以下支持范围和
VM 内存约定为准；能够被宿主 C 编译器接受的程序，不一定能直接在 c4vm 上运行。

已支持的主要功能

- 整数算术、位运算、短路逻辑与三目表达式。
- 函数调用、递归、函数指针和词法作用域。
- if/else、while、do/while、for，以及循环内的 break/continue。
- 指针、显式大小数组、嵌套花括号初始化、基本结构体和联合体字段访问。
- 浮点算术、比较、条件判断，以及整数/浮点之间的显式和隐式转换。

声明与初始化的限制

1. 结构体定义后不能直接接变量声明，也不支持将结构体定义与 typedef 合写：

   ```c
   struct Point { int x; int y; } point;           // 暂不支持
   typedef struct Vector { int x; int y; } Vector; // 暂不支持
   ```

   使用结构体变量时，请把类型定义和变量声明分开：

   ```c
   struct Point { int x; int y; };
   struct Point point;
   ```

2. 数组长度必须显式指定，不能根据初始化列表推导：

   ```c
   int values[] = {1, 2, 3};  // 暂不支持
   int values[3] = {1, 2, 3}; // 支持
   ```

3. 多维数组需要按维度嵌套初始化列表，不支持省略内层花括号：

   ```c
   int flat[2][2] = {1, 2, 3, 4};       // 暂不支持
   int nested[2][2] = {{1, 2}, {3, 4}}; // 支持
   ```

4. 尚不支持结构体、联合体等聚合对象的整体赋值和按值返回，也不支持局部字符
   数组直接使用字符串初始化，例如函数内的 char text[4] = "abc"。

类型转换与浮点运算

整数与浮点之间的数值转换已覆盖以下场景：

- 普通赋值、链式赋值和复合赋值；赋值表达式返回转换后的值。
- 局部/全局变量初始化，以及数组、结构体初始化列表中的标量元素。
- 普通函数和函数指针调用的固定参数，以及函数返回值。
- 混合算术、混合比较、三目表达式，以及显式 cast。

例如，下面的程序会输出 -2 1 1：

```c
#include <stdio.h>

double half(double value) { return value / 2; }
int truncate(double value) { return value; }

int main(void) {
    double x = 3;       // 初始化：3 -> 3.0
    int y = half(5);    // 实参 5 -> 5.0；结果 2.5 -> 2
    x = y;             // 赋值：2 -> 2.0
    printf("%d %d %d", truncate(-2.9), x == 2.0, 1 == 1.0);
    return 0;
}
```

混合算术或比较中，只要一侧是浮点数，就先将整数操作数转换为浮点数。
六种比较 ==、!=、<、>、<=、>= 均按浮点数值执行，而非比较底层整数位模式。
+0.0 与 -0.0 相等；NaN 与任何数比较时，仅 != 为真，其余比较为假。
条件判断、!、&&、|| 中，正负零均为假，其余浮点值（包括 NaN）为真，
逻辑运算保持短路语义。

整数转浮点可能发生精度舍入；浮点转整数向零截断，例如 -2.9 转为 -2。
有符号及无符号整数分别使用对应的转换指令，字符结果再按其 1 字节类型存储。
浮点转整数要求输入有限且截断后的值能被目标类型表示；NaN、无穷大和越界值
不提供定义结果，静态常量中的可检测越界会报告错误。

float 与 double 在当前 VM 中都使用 64 位浮点表示，不模拟宿主的 32 位 float。
这些数值能力不等于完整的标准 C 类型系统，也不扩展下文 printf 的格式支持。

其他尚未支持的语法

- goto 和 switch。
- static、const 等尚未实现的声明说明符或类型限定符。
- 用户定义的可变参数函数，以及完整的 typedef/结构体标签声明组合。
- 整数运算中完整的整型提升、有符号/无符号混合规则和数字字面量后缀。

VM 内存与调用约定

c4vm 使用自己的 ABI，与宿主 C ABI 不兼容：

- char、signed char、unsigned char 占 1 字节；其余标量及指针占 8 字节。
  例如，VM 中的 sizeof(int) 为 8。
- 所有实参槽固定占 8 字节，包括 char 参数；这不改变字符变量本身的存储大小。
- 结构体字段紧密排列，不按宿主 C 编译器的规则插入对齐填充。

因此，不应将 VM 的类型大小、结构体布局或调用约定直接套用到宿主 C 程序。

预处理与内置库的边界

预处理支持对象宏、#undef、#ifdef/#ifndef/#else/#endif，以及带引号的相对路径
include。尚不支持函数宏、#if/#elif、反斜杠续行等完整预处理语义。

尖括号 include 被忽略，常用库功能由 VM 内置函数提供，不会导入完整标准头文件。
printf 支持基本整数、字符、字符串和指针格式，限制为格式串加最多 5 个值；
不支持浮点格式、* 宽度、%n 和宽字符等语义。scanf 最多接受 5 个目标地址，
读取 VM 的 8 字节整数时应使用 %lld。内置函数的参数数量会在编译时检查。

部分不支持的语法仍只有基础诊断，具体问题和后续工作见 docs/AUDIT.txt。
VM 会检查基本镜像头、大小和未知指令，但尚未全面检查访存、跳转与栈边界；
它面向可信的教学程序，不提供运行不可信代码所需的隔离保证。
