#!/usr/bin/env bash
# run_tests.sh — agent-eval-v1.1 合并版测试入口。
# 依赖：PyYAML jsonschema openpyxl jinja2 （pip install -r 要求）
# 用法：bash tests/run_tests.sh
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SKILL_DIR"

echo "============================================================"
echo "agent-eval-v1.1 合并版测试（v1.1 + dev-skill-eval）"
echo "SKILL_DIR=$SKILL_DIR"
echo "python: $(python3 --version 2>&1)"
echo "scripts: $(ls scripts/*.py | wc -l) 个"
echo "============================================================"

FAIL=0

echo ""
echo "[1/2] 单元测试：imports + CLI smoke + Gitee 6 脚本功能"
echo "------------------------------------------------------------"
python3 tests/test_unit.py || FAIL=1

echo ""
echo "[2/2] 端到端 mock：eval_runner → diagnoser → quality → mutation → optimizer → iteration + cost_tracker"
echo "------------------------------------------------------------"
python3 tests/test_e2e_mock.py || FAIL=1

echo ""
echo "============================================================"
if [ "$FAIL" = "0" ]; then
  echo "全部测试通过 ✓"
else
  echo "存在失败用例 ✗"
fi
echo "============================================================"
exit $FAIL
