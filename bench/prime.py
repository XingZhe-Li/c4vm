is_prime = [1] * 100000
for i in range(2,100000):
    if is_prime[i]:
        for j in range(2 * i,100000,i):
            is_prime[j] = 0

for i in range(100000):
    if not is_prime[i]:
        continue
    print("{0},".format(i),end='')