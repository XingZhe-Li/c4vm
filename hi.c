#include <stdio.h>

struct Person {
    long long* base;
};

int main(int argc,char** argv) {
    int x[1] = {321123};
    struct Person bob = {
        .base = x
    };
    printf(
        "%lld %lld %lld",
        (char*)bob.base,
        bob.base[0],
        (char*)bob.base + bob.base[0]
    );
}