int main() {
    if (opcode < OPCODE_END && opcode >= 0) {
        printf(
            "fetch opcode = %.4s\n",
            &"OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,"
            "OPEN,READ,CLOS,PRTF,MALC,FREE,MSET,MCMP,EXIT,SCMP,SLEN,SSTR,SCAT,"[opcode * 5]
        );
    }
}