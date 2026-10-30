"""回归测试的公共辅助函数，临时产物集中在被 Git 忽略的 build/test-temp。"""

from pathlib import Path
import tempfile


def temporary_directory():
    root = Path(__file__).resolve().parents[1] / "build" / "test-temp"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)
