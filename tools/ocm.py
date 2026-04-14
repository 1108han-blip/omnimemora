"""
ocm.py - OpenClaw Shortcut Entry
=================================
固定 --agent openclaw，透传参数给 memrun.py。

用法：
    python ocm.py "summarize the codebase" [--tenant xxx] [--workspace-id ws1]
"""
import subprocess
import sys


def main():
    import os
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    memrun_py = os.path.join(tools_dir, "memrun.py")

    result = subprocess.run(
        [sys.executable, memrun_py, "--agent", "openclaw"] + sys.argv[1:]
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
