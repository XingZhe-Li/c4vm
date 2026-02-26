#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <memory.h>
#include <unistd.h>
#include <fcntl.h>

#ifndef O_RDONLY
#define O_RDONLY 0x0000
#define O_CREAT  0x0100
#define O_WRONLY 0x0001
#define O_TRUNC  0x0200
#endif

// #define C4VM_DEBUG
#define C4VM_NOWRITE
// #define C4VM_VERBOSE

struct c4vm {
    long long  pc,bp,sp,reg;
    long long* base;
};

enum OPCODES { 
    NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,
    OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,
    FADD,FSUB,FMUL,FDIV,I2F ,F2I ,JREG,JSRR,NOT ,WRIT,GETC,
    OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCPY,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,SCNF,OPCODE_END
};

int OPCODE_LEN = sizeof(enum OPCODES);

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
                "OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCPY,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,SCNF,"[opcode * 5]
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
            vm->pc = vm->base[vm->pc++] / 8;
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
            vm->reg = *(long long*)((char*)vm->base + vm->reg);
        } else if (opcode == LC) {
            vm->reg = ((char*)vm->base)[vm->reg];
        } else if (opcode == SI) {
            *(long long*)((char*)vm->base + vm->base[vm->sp++]) = vm->reg;
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
            vm->reg = vm->base[vm->sp++] << vm->reg;
        } else if (opcode == SHR) {
            vm->reg = vm->base[vm->sp++] >> vm->reg;
        } else if (opcode == ADD) {
            vm->reg = vm->base[vm->sp++] + vm->reg;
        } else if (opcode == SUB) {
            vm->reg = vm->base[vm->sp++] - vm->reg;
        } else if (opcode == MUL) {
            vm->reg = vm->base[vm->sp++] * vm->reg;
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
        }

        // JMP with Register
        else if (opcode == JREG) {
            vm->pc  = vm->reg / 8;
        } else if (opcode == JSRR) {
            vm->base[--vm->sp] = (vm->pc+1) * 8;
            vm->pc = vm->reg  / 8;
        } else if (opcode == NOT) {
            vm->reg = ~vm->reg;
        }

        // Library functions
        else if (opcode == OPEN) {
#ifdef C4VM_DEBUG
            printf("OPEN IS FORBIDDEN WHEN WITH C4VM_DEBUG\n");
#else
            vm->reg = open((char*)vm->base + vm->base[vm->sp + 1], vm->base[vm->sp]);
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
            long long arg_offset = vm->sp + vm->base[vm->pc + 1];
            long long argpos = 2;
            char *fmt = (char*)vm->base + vm->base[arg_offset - 1];
            for (char *p = fmt; *p != 0; p++) {
                if (argpos > 6) break;
                if (*p == '%') {
                    p++;
                    while (*p != 0 && !(*p >= 'a' && *p <= 'z') && !(*p >= 'A' && *p <= 'Z')) {
                        p++;
                    }
                    if (*p == 's') {
                        vm->base[arg_offset - argpos] += (long long)vm->base;
                    }
                    argpos++;
                    if (*p == 0) break; 
                }
            }
            vm->reg = printf(
                fmt,
                vm->base[arg_offset - 2],
                vm->base[arg_offset - 3],
                vm->base[arg_offset - 4],
                vm->base[arg_offset - 5],
                vm->base[arg_offset - 6]
            );
        } else if (opcode == MALC) {
            vm->reg = (long long) malloc(vm->base[vm->sp]) - (long long)vm->base;
        } else if (opcode == FREE) {
            free(vm->base + vm->base[vm->sp]);
        } else if (opcode == MSET) {
            vm->reg = (long long) memset((char *)vm->base + vm->base[vm->sp + 2],vm->base[vm->sp + 1],vm->base[vm->sp]) - (long long)vm->base;
        } else if (opcode == MCPY) {
            memcpy((char *)vm->base + vm->base[vm->sp + 2],(char *) vm->base + vm->base[vm->sp + 1],vm->base[vm->sp]);
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
            vm->reg = (long long)((void*)strstr((char *)vm->base + vm->base[vm->sp + 1],(char *)vm->base + vm->base[vm->sp]) - (void*)vm->base);
        } else if (opcode == SCAT) {
            vm->reg = (long long)((void*)strcat((char *)vm->base + vm->base[vm->sp + 1],(char *)vm->base + vm->base[vm->sp]) - (void*)vm->base);
        } else if (opcode == SCNF) {
            long long arg_offset = vm->sp + vm->base[vm->pc + 1];
            vm->reg = scanf((char*)vm->base + vm->base[arg_offset-1],(char*)vm->base + vm->base[arg_offset-2],(char*)vm->base + vm->base[arg_offset-3],(char*)vm->base + vm->base[arg_offset-4],(char*)vm->base + vm->base[arg_offset-5],(char*)vm->base + vm->base[arg_offset-6]);
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
#ifdef C4VM_DEBUG
            printf("unknown instruction = %lld!\n",opcode);
#endif
        }
        
        // FOR DEBUG
        // printf("vm->sp = %lld (%lld,%lld,%lld) , ",vm->sp,vm->base[vm->sp],vm->base[vm->sp+1],vm->base[vm->sp+2]);
        // printf("vm->pc = %lld (%lld,%lld,%lld)",vm->pc,vm->base[vm->pc],vm->base[vm->pc+1],vm->base[vm->pc+2]);
        // getchar();
    }
}

long long load_mem(long long* base,long long space) {
    struct c4vm vm = {
        .bp   = space / sizeof(long long),
        .sp   = space / sizeof(long long),
        .pc   = 0,
        .reg  = 0,
        .base = base,
    };

    long long exit_addr = (vm.sp - 2) * 8;
    vm.base[--vm.sp] = EXIT;
    vm.base[--vm.sp] = PSH;
    vm.base[--vm.sp] = exit_addr;
    
    return run(&vm);
}

long long load(char* filename) {
    long long fd = open(filename,O_RDONLY);
    if (fd == -1) {
        printf("load failed");
        exit(1);
    }

    long long size = 0;
    if (read(fd, &size, sizeof(long long)) != sizeof(long long)) {
        printf("Read size failed\n");
        exit(1);
    }
    
    long long* base = malloc(size);
    if (!base) {
        printf("Malloc failed\n");
        exit(1);
    }

    read(fd,base,size);
    close(fd);

    return load_mem(base,size);
}

void make(long long* base,long long size,long long space,char* filename) {
    long long fd = open(filename,O_WRONLY | O_CREAT | O_TRUNC,0777);
    if (fd == -1) {
        printf("failed when creating file");
        exit(1);
    }

    if (write(fd, &space, sizeof(long long)) != sizeof(long long)) {
        printf("failed when writing header\n");
        close(fd);
        exit(1);
    }

    if (write(fd, base, size) != size) {
        printf("failed when writing payload\n");
        close(fd);
        exit(1);
    }

    close(fd);
    printf("Successfully created image: %s (%lld bytes written)\n", filename, size + 8);
}

long long load_with_args(char* filename,long long argc,char** argv) {
    long long fd = open(filename,O_RDONLY);
    if (fd == -1) {
        printf("load failed");
        exit(1);
    }

    long long size = 0;
    if (read(fd, &size, sizeof(long long)) != sizeof(long long)) {
        printf("Read size failed\n");
        exit(1);
    }
    
    long long* base = malloc(size);
    if (!base) {
        printf("Malloc failed\n");
        exit(1);
    }

    read(fd,base,size);
    close(fd);

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
    for (int i = argc - 1 ; i >= 0 ; i --) {
        vm.base[--vm.sp] = (long long)argv[i] - (long long)vm.base;
    }
    long long argv_virt = vm.sp * 8;
    vm.base[--vm.sp] = argc;
    vm.base[--vm.sp] = argv_virt;
    vm.base[--vm.sp] = exit_addr;

    return run(&vm);
}

int main(int argc,char** argv) {
    if (argc == 1) {
        printf("usage:\tc4vm [image]\n");
    } else {
        load_with_args(argv[1],argc-1,argv+1);
    }
    return 0;
}