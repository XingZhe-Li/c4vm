A virtual machine inspired by c4.c

not supported features:

```
struct x {
    ...
} y;

int arr[] = {1,2,3};

int arr[2][2] = {1,2,3,4};

typedef struct x {} z;

return struct; 

all arguments are resized to 8 bytes when passed as a parameter!

goto is not supported!

static / const are not supported!

auto type conversion like int x = y;
```

ASTNode Types:

```
1.  **结构与作用域**
    * `program`: 程序根节点
    * `actions`: 语句块/作用域容器
    * `function`: 函数定义节点
2.  **控制流语句**
    * `if` / `ifelse`: 条件分支语句
    * `while` / `do_while` / `for`: 循环控制语句
    * `ret`: 返回语句
3.  **赋值与初始化**
    * `assign`: 赋值运算
    * `init_assign`: 带初始化的变量声明
    * `initlist`: 列表初始化内容 `{...}`
4.  **算术与逻辑运算**
    * `add` / `sub` / `mul` / `div` / `mod`: 基础算术
    * `shl` / `shr` / `bitand` / `bitor` / `bitxor` / `bitnot`: 位运算
    * `and` / `or` / `not`: 逻辑运算
    * `cond`: 三目运算符 `? :`
5.  **单目与特殊运算**
    * `incret` / `decret`: 前置自增自减
    * `retinc` / `retdec`: 后置自增自减
    * `addr` / `deaddr`: 取地址与解引用
    * `neg`: 负号运算
    * `sizeof`: 长度计算
    * `as`: 强制类型转换
    * `comma`: 逗号表达式
6.  **访问与调用**
    * `call`: 函数调用
    * `index`: 数组下标访问 `[]`
    * `attr` / `ptr_attr`: 结构体成员访问 `.` 和 `->`
7.  **原子节点 (字面量与引用)**
    * `var`: 变量引用
    * `integer`: 整数字面量
    * `float`: 浮点数字面量
    * `string`: 字符串字面量
```

UNDONE:

as, control flows 