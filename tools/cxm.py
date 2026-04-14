"""
cxm.py - Codex Shortcut Entry
==============================
固定 --agent codex，透传参数给 memrun.py。

用法：
    python cxm.py "explain the auth flow" [--tenant xxx] [--workspace-id ws1]
"""
import subprocess
import sys


def main():
    import os
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    memrun_py = os.path.join(tools_dir, "memrun.py")

    result = subprocess.run(
        [sys.executable, memrun_py, "--agent", "codex"] + sys.argv[1:]
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
