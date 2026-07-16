#!/usr/bin/env python3
"""
XLSX to Markdown - Excel 文件转换为 Markdown 格式

将 Excel 工作表转换为 Markdown 表格格式，支持多工作表。
"""

import os
import argparse
import sys
from pathlib import Path


def get_python_executable():
    """检测合适的 Python 可执行文件"""
    import platform
    system_name = platform.system()

    if system_name == 'Windows':
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
        system_root = os.environ.get('SystemRoot', 'C:\\Windows')
        for path in [
            os.path.join(system_root, 'System32', 'python.exe'),
            os.path.join(system_root, 'SysWOW64', 'python.exe'),
        ]:
            if os.path.exists(path):
                return path
        return "python"
    elif system_name == 'Darwin':
        return "python3"
    else:
        return "python3"


def main():
    """主入口 - 自动解析依赖并执行转换"""
    import platform
    system_name = platform.system()

    # 自动导入 pandas/openpyxl/xlrd
    try:
        import pandas as pd
    except ImportError:
        # 尝试自动安装依赖
        print("检测到缺少依赖库，正在自动安装 pandas 和 openpyxl...")
        python_exe = get_python_executable()
        import subprocess
        subprocess.check_call([python_exe, "-m", "pip", "install", "pandas", "openpyxl", "xlrd"], shell=(system_name == 'Windows'))
        import pandas as pd

    parser = argparse.ArgumentParser(description='XLSX to Markdown 转换工具')
    parser.add_argument('--input', '-i', type=str, default=None,
                        help='输入 Excel 文件路径（或通过环境变量 INPUT_PATH 指定）')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='输出 Markdown 文件路径（或通过环境变量 OUTPUT_PATH 指定）')

    args = parser.parse_args()

    # 优先级：命令行参数 > 环境变量
    input_path = args.input or os.environ.get('INPUT_PATH')
    output_path = args.output or os.environ.get('OUTPUT_PATH')

    if not input_path:
        print("错误：必须指定输入文件路径（--input 或 INPUT_PATH 环境变量）")
        sys.exit(1)

    if not os.path.exists(input_path):
        print(f"错误：输入文件不存在：{input_path}")
        sys.exit(1)

    # 自动生成输出路径
    if output_path is None:
        output_path = os.path.splitext(input_path)[0] + '.md'

    print(f"正在读取：{input_path}")

    # 根据扩展名选择引擎
    ext = os.path.splitext(input_path)[1].lower()
    engine = 'openpyxl' if ext == '.xlsx' else 'xlrd' if ext == '.xls' else 'openpyxl'

    # 读取 Excel 文件
    try:
        xls = pd.ExcelFile(input_path, engine=engine)
    except Exception as e:
        print(f"读取 Excel 文件失败：{e}")
        sys.exit(1)

    # 转义 Markdown 特殊字符
    def escape_markdown(text):
        if pd.isna(text):
            return ""
        text = str(text)
        text = text.replace("\\", "\\\\")
        text = text.replace("|", "\\|")
        text = text.replace("\n", " ")
        return text

    # 生成 Markdown 内容
    markdown_content = []

    for sheet_name in xls.sheet_names:
        print(f"正在转换工作表：{sheet_name}")
        df = pd.read_excel(input_path, sheet_name=sheet_name, engine=engine)

        markdown_content.append(f"# {sheet_name}\n")

        if df.empty:
            markdown_content.append("*工作表为空*\n")
            continue

        columns = df.columns.tolist()
        column_names = [str(col).strip() for col in columns]
        escaped_cols = [escape_markdown(col) for col in column_names]

        markdown_content.append("| " + " | ".join(escaped_cols) + " |")
        markdown_content.append("|" + "|".join(["---"] * len(columns)) + "|")

        for _, row in df.iterrows():
            row_values = [escape_markdown(str(val).strip() if pd.notna(val) else "") for val in row]
            markdown_content.append("| " + " | ".join(row_values) + " |")

        markdown_content.append("\n---\n")

    # 写入 Markdown 文件
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(markdown_content))
        print(f"Markdown 文件已保存至：{output_path}")
        print("转换完成!")
    except Exception as e:
        print(f"写入 Markdown 文件失败：{e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
