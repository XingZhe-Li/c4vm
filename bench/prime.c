#include <stdio.h>
#include <string.h>

int main() {
    int isprimes[100000];
    memset(isprimes,1,sizeof(isprimes));
    for (int i = 2 ; i < 100000 ; i++) {
        if (isprimes[i]) {
            for (int s = 2 * i ; s < 100000 ; s += i ) {
                isprimes[s] = 0;
            }
        }
    }
    for (int i = 0 ; i < 100000 ; i++) {
        if (isprimes[i] == 0) continue;
        printf("%d,",i);
    }
    return 0;
}