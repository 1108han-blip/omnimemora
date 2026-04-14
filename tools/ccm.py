"""
ccm.py - Claude Code Shortcut Entry
====================================
固定 --agent claude_code，透传参数给 memrun.py。

用法：
    python ccm.py "explain this function" [--tenant xxx] [--workspace-id ws1]
"""
import subprocess
import sys


def main():
    # 把 --agent claude_code 固定加在参数列表最前面，
    # 其余所有命令行参数原封不动透传给 memrun.py。
    import os
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    memrun_py = os.path.join(tools_dir, "memrun.py")

    result = subprocess.run(
        [sys.executable, memrun_py, "--agent", "claude_code"] + sys.argv[1:]
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
