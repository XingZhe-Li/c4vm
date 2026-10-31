/*
 * c4vm 的唯一解释器实现：普通构建从 .vm 文件运行程序；
 * tools/build_matrix_in_matrix.py 定义 C4VM_EMBEDDED 后包含本文件，
 * 复用相同的 run/load_mem，仅由生成的包装程序提供 code[] 和 main。
 * 公共执行路径须保持在本项目 C 子集内，才能再次被编译成 VM 字节码。
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>

// #define C4VM_DEBUG
#define C4VM_NOWRITE
// #define C4VM_VERBOSE

struct c4vm {
    /* pc/bp/sp 使用 8 字节字下标；寄存器中的 VM 地址使用字节偏移。 */
    long long  pc,bp,sp,reg;
    long long* base;
};

/* 编号顺序必须与 codegen.py 的 opcode_text 一致；现有编号不可随意重排。 */
enum OPCODES { 
    NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,
    OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,
    FADD,FSUB,FMUL,FDIV,I2F ,F2I ,JREG,JSRR,NOT ,WRIT,GETC,
    OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCPY,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,SCNF,
    FEQ ,FNE ,FLT ,FGT ,FLE ,FGE ,U2F ,F2U ,OPCODE_END
};

/* 避免依赖前端尚未提供的 strchr 内置函数，两种入口共用同一实现。 */
int contains_char(char *text, int value) {
    while (*text) {
        if (*text == value) return 1;
        text++;
    }
    return 0;
}

/* 仅诊断出口区分宿主与嵌入环境；嵌入环境没有 stderr 对象。 */
void vm_report(char *format, long long detail) {
#ifdef C4VM_EMBEDDED
    printf(format, detail);
#else
    fprintf(stderr, format, detail);
#endif
}

/* sp 向低地址增长；跳转/返回地址在指令流和栈中均按字节保存。 */
long long run(struct c4vm* vm) {
    while (1) {
        long long opcode = vm->base[vm->pc++];
#ifdef C4VM_VERBOSE
        if (opcode < OPCODE_END && opcode >= 0) {
            printf(
                "fetch opcode = %.4s\n",
                &"NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,"
                "OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,"
                "FADD,FSUB,FMUL,FDIV,I2F ,F2I ,JREG,JSRR,NOT ,WRIT,GETC,"
                "OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCPY,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,SCNF,"
                "FEQ ,FNE ,FLT ,FGT ,FLE ,FGE ,U2F ,F2U ,"[opcode * 5]
            );
            printf("[PC:%04lld] [SP:%04lld] [BP:%04lld] [REG:0x%llx (%lld)]\n", 
               vm->pc * 8, vm->sp * 8, vm->bp * 8, vm->reg, vm->reg);
        }
#endif
        // Basic Operations
        if (opcode == NOP) {
            continue;
        } else if (opcode == LEA) {
            vm->reg = 8 * vm->bp + vm->base[vm->pc++];
        } else if (opcode == IMM) {
            vm->reg = vm->base[vm->pc++];
        } else if (opcode == JMP) {
            vm->pc  = vm->base[vm->pc] / 8;
        } else if (opcode == JSR) {
            vm->base[--vm->sp] = (vm->pc+1) * 8;
            vm->pc = vm->base[vm->pc] / 8;
        } else if (opcode == BZ) {
            vm->pc  = vm->reg ? vm->pc + 1 : (vm->base[vm->pc] / 8);
        } else if (opcode == BNZ) {
            vm->pc  = vm->reg ? (vm->base[vm->pc] / 8): vm->pc + 1;
        } else if (opcode == ENT) {
            vm->base[--vm->sp] = vm->bp * 8;
            vm->bp  = vm->sp;
            vm->sp -= vm->base[vm->pc++];
        } else if (opcode == ADJ) {
            vm->sp += vm->base[vm->pc++];
        } else if (opcode == LEV) {
            vm->sp = vm->bp;
            vm->bp = vm->base[vm->sp++] / 8;
            vm->pc = vm->base[vm->sp++] / 8;
        } else if (opcode == LI) {
            /* 结构体字段紧密排列，memcpy 允许从未对齐的字节地址读写。 */
            memcpy(&vm->reg, (char*)vm->base + vm->reg, sizeof(vm->reg));
        } else if (opcode == LC) {
            vm->reg = ((signed char*)vm->base)[vm->reg];
        } else if (opcode == SI) {
            memcpy((char*)vm->base + vm->base[vm->sp++], &vm->reg, sizeof(vm->reg));
        } else if (opcode == SC) {
            *((char*)vm->base + vm->base[vm->sp++]) = vm->reg;
        } else if (opcode == PSH) {
            vm->base[--vm->sp] = vm->reg;
        } 
        // Logics & Arithmetics
        else if (opcode == OR) {
            vm->reg = vm->base[vm->sp++] | vm->reg;
        } else if (opcode == XOR) {
            vm->reg = vm->base[vm->sp++] ^ vm->reg;
        } else if (opcode == AND) {
            vm->reg = vm->base[vm->sp++] & vm->reg;
        } else if (opcode == EQ) {
            vm->reg = vm->base[vm->sp++] == vm->reg;
        } else if (opcode == NE) {
            vm->reg = vm->base[vm->sp++] != vm->reg;
        } else if (opcode == LT) {
            vm->reg = vm->base[vm->sp++] < vm->reg;
        } else if (opcode == GT) {
            vm->reg = vm->base[vm->sp++] > vm->reg;
        } else if (opcode == LE) {
            vm->reg = vm->base[vm->sp++] <= vm->reg;
        } else if (opcode == GE) {
            vm->reg = vm->base[vm->sp++] >= vm->reg;
        } else if (opcode == SHL) {
            vm->reg = (unsigned long long)vm->base[vm->sp++] << vm->reg;
        } else if (opcode == SHR) {
            vm->reg = vm->base[vm->sp++] >> vm->reg;
        } else if (opcode == ADD) {
            /* 字运算按 64 位模运算保留位模式，避免无符号值经过宿主有符号溢出。 */
            vm->reg = (unsigned long long)vm->base[vm->sp++] + vm->reg;
        } else if (opcode == SUB) {
            vm->reg = (unsigned long long)vm->base[vm->sp++] - vm->reg;
        } else if (opcode == MUL) {
            vm->reg = (unsigned long long)vm->base[vm->sp++] * vm->reg;
        } else if (opcode == DIV) {
            vm->reg = vm->base[vm->sp++] / vm->reg;
        } else if (opcode == MOD) {
            vm->reg = vm->base[vm->sp++] % vm->reg;            
        } 

        // Floating Point Support (only double , "f64")
        else if (opcode == FADD) {
            double f1,f2,fresult;
            memcpy(&f1,&vm->reg,8);
            memcpy(&f2,&vm->base[vm->sp++],8);
            fresult = f1 + f2;
            memcpy(&vm->reg,&fresult,8);
        } else if (opcode == FSUB) {
            double f1,f2,fresult;
            memcpy(&f1,&vm->reg,8);
            memcpy(&f2,&vm->base[vm->sp++],8);
            fresult = f2 - f1;
            memcpy(&vm->reg,&fresult,8);
        } else if (opcode == FMUL) {
            double f1,f2,fresult;
            memcpy(&f1,&vm->reg,8);
            memcpy(&f2,&vm->base[vm->sp++],8);
            fresult = f1 * f2;
            memcpy(&vm->reg,&fresult,8);
        } else if (opcode == FDIV) {
            double f1,f2,fresult;
            memcpy(&f1,&vm->reg,8);
            memcpy(&f2,&vm->base[vm->sp++],8);
            fresult = f2 / f1;
            memcpy(&vm->reg,&fresult,8); 
        } else if (opcode == I2F) {
            long long ibuf; double fbuf;
            memcpy(&ibuf,&vm->reg,sizeof(long long));
            fbuf = (double) ibuf;
            memcpy(&vm->reg,&fbuf,sizeof(long long));
        } else if (opcode == F2I) {
            long long ibuf; double fbuf;
            memcpy(&fbuf,&vm->reg,sizeof(long long));
            ibuf = (long long) fbuf;
            memcpy(&vm->reg,&ibuf,sizeof(long long));
        } else if (opcode == U2F) {
            unsigned long long ibuf; double fbuf;
            memcpy(&ibuf, &vm->reg, 8);
            fbuf = (double)ibuf;
            memcpy(&vm->reg, &fbuf, 8);
        } else if (opcode == F2U) {
            unsigned long long ibuf; double fbuf;
            memcpy(&fbuf, &vm->reg, 8);
            ibuf = (unsigned long long)fbuf;
            memcpy(&vm->reg, &ibuf, 8);
        } else if (opcode == FEQ || opcode == FNE || opcode == FLT ||
                   opcode == FGT || opcode == FLE || opcode == FGE) {
            /* 解码为 double 后比较：+0.0 == -0.0，NaN 仅使 != 成立。
             * 不能先相减或按整数位模式比较，否则负数、NaN 和无穷大会出错。
             * 新指令追加在表尾，已有镜像的操作码编号保持不变。 */
            double left, right;
            memcpy(&right, &vm->reg, 8);
            memcpy(&left, &vm->base[vm->sp++], 8);
            if (opcode == FEQ) vm->reg = left == right;
            else if (opcode == FNE) vm->reg = left != right;
            else if (opcode == FLT) vm->reg = left < right;
            else if (opcode == FGT) vm->reg = left > right;
            else if (opcode == FLE) vm->reg = left <= right;
            else vm->reg = left >= right;
        }

        // JMP with Register
        else if (opcode == JREG) {
            vm->pc  = vm->reg / 8;
        } else if (opcode == JSRR) {
            vm->base[--vm->sp] = vm->pc * 8;
            vm->pc = vm->reg  / 8;
        } else if (opcode == NOT) {
            vm->reg = ~vm->reg;
        }

        // Library functions
        else if (opcode == OPEN) {
#ifdef C4VM_DEBUG
            printf("OPEN IS FORBIDDEN WHEN WITH C4VM_DEBUG\n");
#else
            long long count = vm->base[vm->pc + 1];
            vm->reg = open((char*)vm->base + vm->base[vm->sp + count - 1],
                           vm->base[vm->sp + count - 2], count == 3 ? vm->base[vm->sp] : 0);
#endif
        } else if (opcode == READ) {
            vm->reg = read(vm->base[vm->sp + 2], (char*)vm->base + vm->base[vm->sp + 1], vm->base[vm->sp]);
        } else if (opcode == CLOS) {
#ifdef C4VM_DEBUG
            printf("CLOS IS FORBIDDEN WHEN WITH C4VM_DEBUG\n");
#else
            vm->reg = close(vm->base[vm->sp]);
#endif
        } else if (opcode == PRTF) {
            /* 编译器紧接着生成 ADJ argc；用它恢复从左到右压栈的参数。 */
            long long arg_offset = vm->sp + vm->base[vm->pc + 1];
            long long args[5] = {0};
            long long count = vm->base[vm->pc + 1] - 1;
            if (count > 5 || count < 0) {
                vm_report("printf supports a format and at most five arguments\n", 0);
                return 1;
            }
            for (long long i = 0; i < count; i++) args[i] = vm->base[arg_offset - 2 - i];
            long long argpos = 0;
            char *fmt = (char*)vm->base + vm->base[arg_offset - 1];
            for (char *p = fmt; *p != 0; p++) {
                if (*p == '%') {
                    p++;
                    if (*p == '%') continue;
                    while (*p && contains_char("-+ #0.123456789hljztL", *p)) p++;
                    if (!*p || !contains_char("diuoxXcsp", *p) || argpos >= count) {
                        vm_report("unsupported printf format or missing argument\n", 0);
                        return 1;
                    }
                    if (*p == 's') {
                        args[argpos] += (long long)vm->base;
                    }
                    argpos++;
                }
            }
            vm->reg = printf(
                fmt, args[0], args[1], args[2], args[3], args[4]
            );
        } else if (opcode == MALC) {
            /* libc 返回宿主指针；编码为相对 base 的偏移，失败则保留 VM 的 0。 */
            void *allocation = malloc(vm->base[vm->sp]);
            vm->reg = allocation ? (long long)allocation - (long long)vm->base : 0;
        } else if (opcode == FREE) {
            if (vm->base[vm->sp]) free((char*)vm->base + vm->base[vm->sp]);
        } else if (opcode == MSET) {
            vm->reg = (long long) memset((char *)vm->base + vm->base[vm->sp + 2],vm->base[vm->sp + 1],vm->base[vm->sp]) - (long long)vm->base;
        } else if (opcode == MCPY) {
            vm->reg = (long long)memcpy((char *)vm->base + vm->base[vm->sp + 2],(char *) vm->base + vm->base[vm->sp + 1],vm->base[vm->sp]) - (long long)vm->base;
        } else if (opcode == MCMP) {
            vm->reg = memcmp((char*)vm->base + vm->base[vm->sp + 2],(char*)vm->base + vm->base[vm->sp + 1],vm->base[vm->sp]);
        } else if (opcode == EXIT) {
#ifdef C4VM_DEBUG
            printf("program exited with %lld\n",vm->base[vm->sp]);
#endif
            return vm->base[vm->sp];
        } 
        
        // My Extensions
        else if (opcode == SCMP) {
            vm->reg = strcmp((char *)vm->base + vm->base[vm->sp + 1],(char *)vm->base + vm->base[vm->sp]);
        } else if (opcode == SLEN) {
            vm->reg = strlen((char *)vm->base + vm->base[vm->sp]);
        } else if (opcode == SSTR) {
            char *found = strstr((char *)vm->base + vm->base[vm->sp + 1],(char *)vm->base + vm->base[vm->sp]);
            vm->reg = found ? (long long)found - (long long)vm->base : 0;
        } else if (opcode == SCAT) {
            char *destination = (char *)vm->base + vm->base[vm->sp + 1];
            char *source = (char *)vm->base + vm->base[vm->sp];
            /* 使用公共子集可编译的拷贝，避免引入另一份宿主专用实现。 */
            long long length = strlen(destination);
            while (*source) destination[length++] = *source++;
            destination[length] = 0;
            vm->reg = vm->base[vm->sp + 1];
        } else if (opcode == SCNF) {
            long long arg_offset = vm->sp + vm->base[vm->pc + 1];
            void *args[5] = {0};
            long long count = vm->base[vm->pc + 1] - 1;
            if (count < 0 || count > 5) {
                vm_report("scanf supports a format and at most five destinations\n", 0);
                return 1;
            }
            for (long long i = 0; i < count; i++) args[i] = (char*)vm->base + vm->base[arg_offset - 2 - i];
            vm->reg = scanf((char*)vm->base + vm->base[arg_offset-1], args[0], args[1], args[2], args[3], args[4]);
        } else if (opcode == WRIT) {
#ifdef C4VM_DEBUG
            printf("WRIT IS FORBIDDEN WHEN WITH C4VM_DEBUG\n");
#else
#ifdef C4VM_NOWRITE
            printf("WRIT IS FORBIDDEN WHEN WITH C4VM_NOWRITE\n");
#else
            vm->reg = write(vm->base[vm->sp + 2],(char*)vm->base + vm->base[vm->sp + 1],vm->base[vm->sp]);
#endif
#endif
        } else if (opcode == GETC) {
            vm->reg = getchar();
        }
        
        // Unknown instruction
        else {
            vm_report("unknown instruction = %lld\n", opcode);
            return 1;
        }
        
    }
}

/* base 同时容纳镜像和预留栈；嵌入入口不传递 argc/argv。space 单位为字节。 */
long long load_mem(long long* base,long long space) {
    if (space < 32 || space % 8 != 0) {
        vm_report("invalid embedded VM memory size\n", 0);
        return 1;
    }
    struct c4vm vm = {
        .bp   = space / sizeof(long long),
        .sp   = space / sizeof(long long),
        .pc   = 0,
        .reg  = 0,
        .base = base,
    };

    long long exit_addr = (vm.sp - 2) * 8;
    /* main 执行 LEV 后返回到栈尾的 PSH/EXIT，将 reg 作为退出状态。 */
    vm.base[--vm.sp] = EXIT;
    vm.base[--vm.sp] = PSH;
    vm.base[--vm.sp] = exit_addr;
    
    return run(&vm);
}

/* 文件加载和宿主 main 不参与嵌套编译，避免依赖 FILE 等子集外类型。 */
#ifndef C4VM_EMBEDDED
long long load_with_args(char* filename,long long argc,char** argv) {
    FILE *image = fopen(filename, "rb");
    if (!image) {
        perror(filename);
        return 1;
    }
    long long size = 0;
    /* 文件头为 8 字节小端虚拟容量；文件剩余部分为原始镜像，不含预留栈。 */
    long long frame = (argc + 7) * 8;
    if (fread(&size, 1, 8, image) != 8 || size < frame || size % 8 != 0 ||
        fseek(image, 0, SEEK_END) != 0) {
        fprintf(stderr, "invalid VM image header\n");
        fclose(image);
        return 1;
    }
    long payload = ftell(image) - 8;
    if (payload < 16 || payload > size - frame || fseek(image, 8, SEEK_SET) != 0) {
        fprintf(stderr, "invalid VM image payload or insufficient stack space\n");
        fclose(image);
        return 1;
    }
    long long *base = calloc(1, size);
    if (!base) {
        fprintf(stderr, "cannot allocate VM memory\n");
        fclose(image);
        return 1;
    }
    if (fread(base, 1, payload, image) != (size_t)payload) {
        fprintf(stderr, "cannot read VM image payload\n");
        free(base);
        fclose(image);
        return 1;
    }
    fclose(image);

    struct c4vm vm = {
        .bp   = size / sizeof(long long),
        .sp   = size / sizeof(long long),
        .pc   = 0,
        .reg  = 0,
        .base = base,
    };

    long long exit_addr = (vm.sp - 2) * 8;
    vm.base[--vm.sp] = EXIT;
    vm.base[--vm.sp] = PSH;
    vm.base[--vm.sp] = 0; /* argv[argc] */
    for (int i = argc - 1 ; i >= 0 ; i --) {
        vm.base[--vm.sp] = (long long)argv[i] - (long long)vm.base;
    }
    long long argv_virt = vm.sp * 8;
    /* 与普通调用相同，按声明顺序压入 argc/argv，最后压入返回地址。 */
    vm.base[--vm.sp] = argc;
    vm.base[--vm.sp] = argv_virt;
    vm.base[--vm.sp] = exit_addr;

    long long result = run(&vm);
    free(base);
    return result;
}

int main(int argc,char** argv) {
    if (argc == 1) {
        printf("usage:\tc4vm [image]\n");
    } else {
        return (int)load_with_args(argv[1],argc-1,argv+1);
    }
    return 0;
}
#endif
