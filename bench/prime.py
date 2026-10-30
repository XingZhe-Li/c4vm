"""与 prime.c 等价的质数筛负载；输出顺序/格式一致，供基准先校验再计时。"""

is_prime = [1] * 100000
for i in range(2,100000):
    if is_prime[i]:
        for j in range(2 * i,100000,i):
            is_prime[j] = 0

for i in range(2,100000):
    if not is_prime[i]:
        continue
    print("{0},".format(i),end='')
