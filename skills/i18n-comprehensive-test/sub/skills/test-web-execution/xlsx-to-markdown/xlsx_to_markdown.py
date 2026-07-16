#!/usr/bin/env python3
"""
XLSX to Markdown Skill - 固化调用脚本

此脚本作为 skill 的直接入口，支持 Windows 和 Linux 系统。
"""

import os
import argparse
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError as e:
    print(f"缺少依赖库：{e}")
    print("请先安装依赖：pip install pandas openpyxl xlrd")
    sys.exit(1)


def get_markdown_path_from_excel(excel_path):
    """根据 Excel 文件路径生成对应的 Markdown 文件路径"""
    return os.path.splitext(excel_path)[0] + '.md'


def escape_markdown(text):
    """转义 Markdown 特殊字符"""
    if pd.isna(text):
        return ""
    text = str(text)
    # 转义 Markdown 特殊字符
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\n", " ")
    return text


def xlsx_to_markdown(input_path, output_path=None):
    """
    将 XLSX 文件转换为 Markdown

    参数:
        input_path: Excel 文件路径
        output_path: Markdown 文件路径（可选，默认：与输入文件同目录）

    返回:
        bool: 转换是否成功
    """
    # 如果未指定输出路径，自动生成
    if output_path is None:
        output_path = get_markdown_path_from_excel(input_path)

    # 检查输入文件是否存在
    if not os.path.exists(input_path):
        print(f"错误：输入文件不存在：{input_path}")
        return False

    print(f"正在读取：{input_path}")

    # 根据扩展名选择引擎
    ext = os.path.splitext(input_path)[1].lower()
    engine = 'openpyxl' if ext == '.xlsx' else 'xlrd' if ext == '.xls' else 'openpyxl'

    # 读取 Excel 文件
    try:
        xls = pd.ExcelFile(input_path, engine=engine)
    except Exception as e:
        print(f"读取 Excel 文件失败：{e}")
        return False

    # 生成 Markdown 内容
    markdown_content = []

    # 遍历每个工作表
    for sheet_name in xls.sheet_names:
        print(f"正在转换工作表：{sheet_name}")
        df = pd.read_excel(input_path, sheet_name=sheet_name, engine=engine)

        # 添加工作表标题
        markdown_content.append(f"# {sheet_name}\n")

        # 转换为 Markdown 表格
        if df.empty:
            markdown_content.append("*工作表为空*\n")
            continue

        # 获取列名
        columns = df.columns.tolist()
        column_names = [str(col).strip() for col in columns]

        # 转义列名中的特殊字符
        escaped_cols = [escape_markdown(col) for col in column_names]

        # 添加表头
        markdown_content.append("| " + " | ".join(escaped_cols) + " |")

        # 添加分隔行
        markdown_content.append("|" + "|".join(["---"] * len(columns)) + "|")

        # 添加数据行
        for _, row in df.iterrows():
            row_values = [escape_markdown(str(val).strip() if pd.notna(val) else "") for val in row]
            markdown_content.append("| " + " | ".join(row_values) + " |")

        markdown_content.append("\n---\n")

    # 写入 Markdown 文件
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(markdown_content))
        print(f"Markdown 文件已保存至：{output_path}")
        return True
    except Exception as e:
        print(f"写入 Markdown 文件失败：{e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='XLSX to Markdown 转换工具')
    parser.add_argument('--input', '-i', type=str, default=None,
                        help='输入 Excel 文件路径（或通过环境变量 INPUT_PATH 指定）')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='输出 Markdown 文件路径（或通过环境变量 OUTPUT_PATH 指定）')

    args = parser.parse_args()

    # 优先级：命令行参数 > 环境变量 > 自动生成
    input_path = args.input or os.environ.get('INPUT_PATH')
    output_path = args.output or os.environ.get('OUTPUT_PATH')

    if not input_path:
        print("错误：必须指定输入文件路径（--input 或 INPUT_PATH 环境变量）")
        sys.exit(1)

    # 自动生成输出路径（与输入文件同目录）
    if output_path is None:
        output_path = get_markdown_path_from_excel(input_path)

    # 检查输入文件
    if not os.path.exists(input_path):
        print(f"错误：输入文件不存在：{input_path}")
        sys.exit(1)

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

    # 生成 Markdown 内容
    markdown_content = []

    # 统计信息
    sheet_count = 0

    # 遍历每个工作表
    for sheet_name in xls.sheet_names:
        sheet_count += 1
        print(f"正在转换工作表：{sheet_name}")
        df = pd.read_excel(input_path, sheet_name=sheet_name, engine=engine)

        # 添加工作表标题
        markdown_content.append(f"# {sheet_name}\n")

        # 转换为 Markdown 表格
        if df.empty:
            markdown_content.append("*工作表为空*\n")
            continue

        # 获取列名
        columns = df.columns.tolist()
        column_names = [str(col).strip() for col in columns]

        # 转义列名中的特殊字符
        escaped_cols = [escape_markdown(col) for col in column_names]

        # 添加表头
        markdown_content.append("| " + " | ".join(escaped_cols) + " |")

        # 添加分隔行
        markdown_content.append("|" + "|".join(["---"] * len(columns)) + "|")

        # 添加数据行
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
