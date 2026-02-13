#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <memory.h>
#include <unistd.h>
#include <fcntl.h>

#define C4VM_DEBUG
// #define C4VM_VERBOSE

struct c4vm {
    long long  pc,bp,sp,reg;
    long long* base;
};

enum OPCODES { 
    NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,
    OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,
    OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,OPCODE_END
};

static int OPCODE_LEN = sizeof(enum OPCODES);

long long run(struct c4vm* vm) {
    while (1) {
        long long opcode = vm->base[vm->pc++];
#ifdef C4VM_VERBOSE
        if (opcode < OPCODE_END && opcode >= 0) {
            printf(
                "fetch opcode = %.4s\n",
                &"NOP ,LEA ,IMM ,JMP ,JSR ,BZ  ,BNZ ,ENT ,ADJ ,LEV ,LI  ,LC  ,SI  ,SC  ,PSH ,"
                "OR  ,XOR ,AND ,EQ  ,NE  ,LT  ,GT  ,LE  ,GE  ,SHL ,SHR ,ADD ,SUB ,MUL ,DIV ,MOD ,"
                "OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,"[opcode * 5]
            );
        }
#endif
        // Basic Operations
        if (opcode == NOP) {
            continue;
        } else if (opcode == LEA) {
            vm->reg = vm->base[vm->bp+vm->base[vm->pc++]];
        } else if (opcode == IMM) {
            vm->reg = vm->base[vm->pc++];
        } else if (opcode == JMP) {
            vm->pc  = vm->base[vm->pc];
        } else if (opcode == JSR) {
            vm->base[--vm->sp] = vm->pc+1;
            vm->pc = vm->base[vm->pc++];
        } else if (opcode == BZ) {
            vm->pc  = vm->reg ? vm->pc + 1 : vm->base[vm->pc];
        } else if (opcode == BNZ) {
            vm->pc  = vm->reg ? vm->base[vm->pc] : vm->pc + 1;
        } else if (opcode == ENT) {
            vm->base[--vm->sp] = vm->bp;
            vm->bp  = vm->sp;
            vm->sp -= vm->base[vm->pc++];
        } else if (opcode == ADJ) {
            vm->sp += vm->base[vm->pc++];
        } else if (opcode == LEV) {
            vm->sp = vm->bp;
            vm->bp = vm->base[vm->sp++];
            vm->pc = vm->base[vm->sp++];
        } else if (opcode == LI) {
            vm->reg = vm->base[vm->reg];
        } else if (opcode == LC) {
            vm->reg = ((char*)vm->base)[vm->reg];
        } else if (opcode == SI) {
            vm->base[vm->sp++] = vm->reg;
        } else if (opcode == SC) {
            ((char*)vm->base)[vm->sp++] = vm->reg;
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
            vm->reg = open((char*)vm->base + vm->base[vm->sp + 1], vm->base[vm->sp]);
#endif
        } else if (opcode == PRTF) {
            long long arg_offset = vm->sp + vm->base[vm->pc + 1];
            vm->reg = printf((char*)vm->base + vm->base[arg_offset-1],vm->base[arg_offset-2],vm->base[arg_offset-3],vm->base[arg_offset-4],vm->base[arg_offset-5],vm->base[arg_offset-6]);
        } else if (opcode == MALC) {
            vm->reg = (long long) malloc(vm->base[vm->sp]) - (long long)vm->base;
        } else if (opcode == FREE) {
            free(vm->base + vm->base[vm->sp]);
        } else if (opcode == MSET) {
            vm->reg = (long long) memset((char *)vm->base + vm->base[vm->sp + 2],vm->base[vm->sp + 1],vm->base[vm->sp]) - (long long)vm->base;
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
        }
        
        // Unknown instruction
        else {
#ifdef C4VM_DEBUG
            printf("unknown instruction = %lld!\n",opcode);
#endif
        }
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

void hi_demo() {
    long long text[4096] = {
        IMM,0,PSH,
        IMM,750245352958211171,PSH,
        IMM,8 * (4096 - 2),PSH,
        PRTF,ADJ,1,
        IMM,0,PSH,
        EXIT
    };

    struct c4vm vm = {
        .bp   = sizeof(text) / sizeof(long long),
        .sp   = sizeof(text) / sizeof(long long),
        .pc   = 0,
        .reg  = 0,
        .base = text,
    };
    run(&vm);
}

int main() {

    long long text[] = {
        IMM,0,PSH,
        IMM,750245352958211171,PSH,
        IMM,8 * (256 - 2),PSH,
        PRTF,ADJ,1,
        IMM,0,PSH,
        EXIT
    };

    make(text,sizeof(text),2048,"output.image");
    load("output.image");

    return 0;
}