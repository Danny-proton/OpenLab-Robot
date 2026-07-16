#!/usr/bin/env python3
"""
测试用例 Markdown 转 Excel Skill - 入口脚本

此文件作为 skill 的直接入口，通过 Bash 调用时自动处理路径。
"""

import os
import sys
import subprocess
import platform
import json


def get_skill_directory():
    """获取技能目录"""
    return os.path.dirname(os.path.abspath(__file__))


def get_python_executable():
    """
    检测合适的 Python 可执行文件
    Windows 优先使用完整路径，Linux/macOS 使用 python3
    """
    system_name = platform.system()

    if system_name == 'Windows':
        # 检查常见安装位置
        candidates = [
            r"C:\Python310\python.exe",
            r"C:\Python39\python.exe",
            r"C:\Python38\python.exe",
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Python310\python.exe"),
            os.path.expanduser(r"~\AppData\Local\Programs\Python\Python39\python.exe"),
        ]

        for path in candidates:
            expanded = os.path.expanduser(path)
            if os.path.exists(expanded):
                return expanded

        # 检查 System32
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        for path in [
            os.path.join(system_root, 'System32', 'python.exe'),
            os.path.join(system_root, 'SysWOW64', 'python.exe'),
        ]:
            if os.path.exists(path):
                return path

        return "python"
    elif system_name == 'Darwin':
        # macOS
        return "python3"
    else:
        # Linux 和其他 Unix 系统
        return "python3"


def main():
    """主入口"""
    script_dir = get_skill_directory()
    actual_script = os.path.join(script_dir, 'testcase_to_xlsx.py')
    python_exe = get_python_executable()
    system_name = platform.system()

    # 构建命令
    cmd = [python_exe, actual_script] + sys.argv[1:]

    # 根据操作系统选择执行方式
    if system_name == 'Windows':
        # Windows 使用 subprocess 直接执行
        try:
            result = subprocess.run(cmd, shell=False)
            sys.exit(result.returncode)
        except FileNotFoundError:
            print(f"错误：无法找到 Python 解释器：{python_exe}", file=sys.stderr)
            sys.exit(1)
    else:
        # Linux/macOS 使用 shell 执行
        try:
            subprocess.run(cmd, check=False)
        except KeyboardInterrupt:
            sys.exit(130)


if __name__ == '__main__':
    main()
