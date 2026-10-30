"""构建原生/VM 质数筛并核对 Python 输出后计时，产物写入 build/bench。

记录的墙钟时间包含进程启动和输出处理，适合作为整体运行开销的简易比较。
"""

import argparse
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import compiler


def perf(command, runs):
    start = time.perf_counter()
    for _ in range(runs):
        subprocess.run(command, stdout=subprocess.DEVNULL, check=True)
    return (time.perf_counter() - start) / runs


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--runs", type=int, default=5)
    args = cli.parse_args()
    if args.runs < 1:
        cli.error("--runs must be positive")
    build = ROOT / "build" / "bench"
    build.mkdir(parents=True, exist_ok=True)
    suffix = ".exe" if os.name == "nt" else ""
    native, vm, image = build / ("prime" + suffix), build / ("c4vm" + suffix), build / "prime.vm"
    command = os.environ.get("CC", "gcc")
    cc = [command] if Path(command).is_file() else shlex.split(command)
    subprocess.run([*cc, "-std=c11", "-O2", str(ROOT / "bench" / "prime.c"), "-o", str(native)], check=True)
    subprocess.run([*cc, "-std=c11", "-O2", str(ROOT / "c4vm.c"), "-o", str(vm)], check=True)
    compiler.compile(str(ROOT / "bench" / "prime.c"), str(image))
    commands = {"native C": [str(native)], "Python": [sys.executable, str(ROOT / "bench" / "prime.py")],
                "c4vm": [str(vm), str(image)]}
    outputs = [subprocess.check_output(command) for command in commands.values()]
    if len(set(outputs)) != 1:
        raise SystemExit("benchmark outputs differ")
    print("Outputs match; mean wall time includes process startup:")
    for name, command in commands.items():
        print(f"{name:8s} {perf(command, args.runs):.6f} s")


if __name__ == "__main__":
    main()
