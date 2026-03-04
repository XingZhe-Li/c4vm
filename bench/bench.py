import os
import time

def perf(cmd,T : int = 10):
    accT = 0
    for _ in range(T):
        start_time = time.time()
        os.system(cmd)
        end_time   = time.time()
        accT += end_time - start_time
    return accT / T

t_c  = perf("prime.exe > nul")
t_py = perf("python prime.py  > nul")
t_vm = perf("c4vm prime.vm  > nul")

print('t_c  = ',t_c )
print('t_py = ',t_py)
print('t_vm = ',t_vm)

'''
t_c  =  0.02026355266571045
t_py =  0.0609661340713501
t_vm =  0.08830926418304444
'''