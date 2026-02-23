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
```