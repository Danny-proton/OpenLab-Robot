"""
手机银行智能体评测 - 需求分析（机械 I/O 层）

本脚本只做三件机械工作（不调用任何 LLM）：
  1. --write-stdout  : 把 Agent 生成好的 JSON 写成 Excel（requirements_analysis.xlsx）
  2. --list          : 列出指定 Excel 中的测试维度
  3. --read          : 把指定 Excel 读成 JSON 输出到 stdout（供下游脚本/Agent 消费）

prompt 拼装和用例生成由 Agent（Claude）在子 skill
`skills/requirements-analysis/SKILL.md` 中用文字指示，通过 Task 工具完成。
本脚本与任何外部模型 URL、API key 完全解耦。

Usage
-----
# 写入：Agent 把生成的 JSON 通过 stdin 传入（或 --json-file 指定文件）
cat agent_generated.json | python generate_requirements.py --write-stdin --output out.xlsx
python generate_requirements.py --write-file --json-file agent_generated.json --output out.xlsx

# 列出维度
python generate_requirements.py --list out.xlsx

# 读回 JSON
python generate_requirements.py --read out.xlsx

agent_generated.json schema:
{
  "dimensions": [
    {"id": "DIM-001", "name": "维度名称", "type": "覆盖类型"}
  ],
  "scenarios": [
    {"id": "SC-001", "dimension": "DIM-001", "name": "子场景", "description": "描述"}
  ],
  "skill_suggestions": [
    {"dimension_id": "DIM-001", "dimension_name": "维度名称", "skill": "所属Skill", "reason": "理由"}
  ]
}
"""
import sys
import json
import os
import argparse
import csv


def main():
    parser = argparse.ArgumentParser(
        description="需求分析机械 I/O 层（无 LLM）。prompt 和生成由 Agent 在子 skill 中完成。"
    )
    parser.add_argument("--write-stdin", action="store_true",
                        help="从 stdin 读取 Agent 生成的 JSON，写成 Excel")
    parser.add_argument("--write-file", action="store_true",
                        help="从 --json-file 读取 Agent 生成的 JSON，写成 Excel")
    parser.add_argument("--json-file", default=None,
                        help="Agent 生成的 JSON 文件路径（配合 --write-file）")
    parser.add_argument("--output", default=None,
                        help="输出 Excel 文件路径")
    parser.add_argument("--list", default=None,
                        help="列出指定 Excel 中的维度信息")
    parser.add_argument("--read", default=None,
                        help="把指定 Excel 读成 JSON 输出到 stdout")
    args = parser.parse_args()

    # 模式 1: 列出维度
    if args.list:
        _list_dimensions(args.list)
        return

    # 模式 2: 读回 JSON
    if args.read:
        data = _read_excel_to_json(_resolve_path(args.read))
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    # 模式 3: 写 Excel
    if args.write_stdin:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(f"[ERROR] stdin 不是合法 JSON: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.write_file:
        if not args.json_file:
            print("[ERROR] --write-file 需要同时给 --json-file", file=sys.stderr)
            sys.exit(1)
        with open(_resolve_path(args.json_file), "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                print(f"[ERROR] json-file 不是合法 JSON: {e}", file=sys.stderr)
                sys.exit(1)
    else:
        parser.print_help(sys.stderr)
        print("\n[ERROR] 必须指定 --write-stdin / --write-file / --list / --read 之一", file=sys.stderr)
        sys.exit(1)

    # 校验最小 schema
    if not isinstance(data, dict) or "dimensions" not in data:
        print("[ERROR] JSON 必须包含 dimensions 字段（list）", file=sys.stderr)
        sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    data_output = os.path.join(script_dir, "..", "data", "requirements_analysis.xlsx")
    output_path = args.output or data_output
    output_path = os.path.abspath(output_path)

    try:
        if os.path.exists(output_path):
            os.remove(output_path)
        _write_excel(data, output_path)
        # 同时刷一份到默认 data/ 位置，方便后续阶段默认路径读取
        default_path = os.path.abspath(data_output)
        if output_path != default_path:
            if os.path.exists(default_path):
                os.remove(default_path)
            _write_excel(data, default_path)
    except ImportError:
        # openpyxl 不可用时降级 CSV
        csv_dir = output_path.replace(".xlsx", "")
        _write_csv(data, csv_dir)
        print(f"[OK] openpyxl 不可用，CSV 降级 -> {csv_dir}_*.csv", file=sys.stderr)
        return

    dims = data.get("dimensions", [])
    scs = data.get("scenarios", [])
    saved_size = os.path.getsize(output_path) if os.path.exists(output_path) else 0
    # stderr 给人看，stdout 给 Agent 解析
    print(f"[阶段 1/4] 需求分析 Excel 写入完成", file=sys.stderr)
    print(f"产出文件：{output_path} ({saved_size} bytes)", file=sys.stderr)
    print(f"dimensions: {len(dims)}, scenarios: {len(scs)}", file=sys.stderr)

    print(json.dumps({
        "stage": 1,
        "status": "ok",
        "output": output_path,
        "dimensions_count": len(dims),
        "scenarios_count": len(scs),
        "dimensions": [
            {"id": d.get("id", ""), "name": d.get("name", ""), "type": d.get("type", "")}
            for d in dims
        ],
    }, ensure_ascii=False, indent=2))


def _resolve_path(path):
    """解析文件路径，若不存在则尝试从 SESSION_OUTPUT_DIR/dataset/ 下查找。"""
    path = os.path.abspath(path)
    if os.path.exists(path):
        return path
    sess_out = os.getenv("SESSION_OUTPUT_DIR", "")
    if sess_out:
        alt = os.path.join(sess_out, "dataset", os.path.basename(path))
        if os.path.exists(alt):
            return alt
    return path


def _list_dimensions(path):
    path = _resolve_path(path)
    if not os.path.exists(path):
        print(f"[ERROR] 文件不存在: {path}", file=sys.stderr)
        sys.exit(1)
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    if "测试维度" not in wb.sheetnames:
        print("[ERROR] Excel 中没有 '测试维度' sheet", file=sys.stderr)
        sys.exit(1)
    ws = wb["测试维度"]
    print("测试维度列表：")
    for row in ws.iter_rows(min_row=2, values_only=True):
        if row and row[0]:
            print(f"  {row[0]} - {row[1]} ({row[2]})")


def _read_excel_to_json(path):
    """把 requirements_analysis.xlsx 读回 JSON（供下游 Agent/脚本消费）。"""
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True)
    data = {"dimensions": [], "scenarios": [], "skill_suggestions": []}
    if "测试维度" in wb.sheetnames:
        ws = wb["测试维度"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                data["dimensions"].append({
                    "id": str(row[0]),
                    "name": str(row[1] or ""),
                    "type": str(row[2] or ""),
                })
    if "测试场景" in wb.sheetnames:
        ws = wb["测试场景"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                data["scenarios"].append({
                    "id": str(row[0]),
                    "dimension": str(row[1] or ""),
                    "name": str(row[2] or ""),
                    "description": str(row[3] or ""),
                })
    if "Skill归属建议" in wb.sheetnames:
        ws = wb["Skill归属建议"]
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row and row[0]:
                data["skill_suggestions"].append({
                    "dimension_id": str(row[0]),
                    "dimension_name": str(row[1] or ""),
                    "skill": str(row[2] or ""),
                    "reason": str(row[3] or ""),
                })
    return data


def _write_excel(data: dict, path: str):
    from openpyxl import Workbook

    wb = Workbook()

    ws1 = wb.active
    ws1.title = "测试维度"
    ws1.append(["维度 ID", "维度名称", "覆盖类型"])
    for dim in data.get("dimensions", []):
        ws1.append([dim.get("id", ""), dim.get("name", ""), dim.get("type", "")])

    ws2 = wb.create_sheet("测试场景")
    ws2.append(["场景 ID", "所属维度", "子场景", "描述"])
    for sc in data.get("scenarios", []):
        ws2.append([
            sc.get("id", ""),
            sc.get("dimension", ""),
            sc.get("name", ""),
            sc.get("description", ""),
        ])

    suggestions = data.get("skill_suggestions", [])
    if suggestions:
        ws3 = wb.create_sheet("Skill归属建议")
        ws3.append(["维度 ID", "维度名称", "归属 Skill", "说明"])
        for s in suggestions:
            ws3.append([
                s.get("dimension_id", ""),
                s.get("dimension_name", ""),
                s.get("skill", ""),
                s.get("reason", ""),
            ])

    os.makedirs(os.path.dirname(path), exist_ok=True)
    wb.save(path)


def _write_csv(data: dict, base_path: str):
    os.makedirs(os.path.dirname(base_path), exist_ok=True)

    dim_path = base_path + "_dimensions.csv"
    with open(dim_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["维度 ID", "维度名称", "覆盖类型"])
        for dim in data.get("dimensions", []):
            w.writerow([dim.get("id", ""), dim.get("name", ""), dim.get("type", "")])

    sc_path = base_path + "_scenarios.csv"
    with open(sc_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["场景 ID", "所属维度", "子场景", "描述"])
        for sc in data.get("scenarios", []):
            w.writerow([
                sc.get("id", ""),
                sc.get("dimension", ""),
                sc.get("name", ""),
                sc.get("description", ""),
            ])

    suggestions = data.get("skill_suggestions", [])
    if suggestions:
        sk_path = base_path + "_skill_suggestions.csv"
        with open(sk_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["维度 ID", "维度名称", "归属 Skill", "说明"])
            for s in suggestions:
                w.writerow([
                    s.get("dimension_id", ""),
                    s.get("dimension_name", ""),
                    s.get("skill", ""),
                    s.get("reason", ""),
                ])


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        import traceback
        traceback.print_exc()
        sys.exit(1)
