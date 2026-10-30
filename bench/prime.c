/* 原生 C 与 VM 共用的质数筛负载；输出所有小于 100000 的素数以校验结果。 */

#include <stdio.h>
#include <string.h>

int main() {
    int isprimes[100000];
    /* 这里只检测零/非零：逐字节填 1 在宿主和 VM 的不同整数宽度下都成立。 */
    memset(isprimes,1,sizeof(isprimes));
    for (int i = 2 ; i < 100000 ; i++) {
        if (isprimes[i]) {
            for (int s = 2 * i ; s < 100000 ; s += i ) {
                isprimes[s] = 0;
            }
        }
    }
    for (int i = 2 ; i < 100000 ; i++) {
        if (isprimes[i] == 0) continue;
        printf("%d,",i);
    }
    return 0;
}
