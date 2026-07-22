需要为Openlab-Robot客户端中新增一个「新建测试任务」的页签，主要概念如下

在"新建会话"下新增按钮"新建测试任务"，测试任务有三种，测试设计、测试执行、Agent评测，我们先做批量测试执行的页签，剩下先置灰，注意页签内要尽量丰富动效

用户点击新建执行任务页签后进入到覆盖中右侧的执行任务管理界面，最右侧是展示当前在流程的多个环节的缩略图，展示当前在哪个环节，已经执行了哪些环节还未做哪些环节，哪些环节已经被执行或确认过了

批量执行任务会单独新建一个文件夹和项目名同名，作为工作区，历史执行过的批量任务可以在右侧侧边栏查到

输出 5 张页面：

1、新建执行任务

测试用例所在文件，模板下载，上传，路径，导入后变成用例卡片，也可以直接导入任务json，还有从TAAS拉取的功能未来支持暂时置灰

新建任务首先需要命名一个项目名，默认按照第一个用例名+等用例执行+时间，可以手动编辑

上传后展示一格格的测试用例，每个包含用例名、预置条件、测试步骤、预期结果，然后会完成用例自检，给出质量评级，调用一个外部的质检包，先包括是否包含四个步骤的字段完整性、步骤数量不低于3步不超过150步、是否包含"应该"、"必须"等验证性词汇等自动化检查项，后续增加LLM评估项，按照出错个数给出质量评级，出现带红黄绿色的角标

可以编辑用例卡片之间的依赖关系，有依赖关系的用例可以像纸牌一样叠放，鼠标拖动用例卡片的时候可以有点交互动效，叠放的时候要有动效，已经叠放的用例可以点开分别编辑每个用例，要有个动效

然后需要设置重复执行次数、失败重试次数、单批执行个数三个数字

点击确认用例设置后进入下一个卡片

2、执行任务设置

这个也可以导入json，或者已经导入过json了直接展示结果

新建的任务包括并行和批次两种，批次内用例全都执行完了才能执行下一个批次，同一批次内可以设置并行用例，这方面需要有个说明

默认执行命令是 @test-web-execution +默认用例执行命令+用例内容

允许修改命名模板重新生成任务上的命令

因为上一个步骤设置过所以这一页可以自动生成一版任务

每个串行任务独占一行，重复执行、失败重试、依赖用例的有叠放，叠放可以展开，展开后子任务有缩进和虚线，并行任务在同一行，不同批次有分割线

也允许单个编辑命令内容

允许重新拖放任务顺序，允许拖放到不同的分割线里，放到任务右侧可以设置并行，放中间和左侧可以设置分组叠放

完成设置后进入到执行卡片

3、任务执行过程*N个批次

有多少个批次就会多出几个右侧的执行缩略卡片，一个变多个要有动效

执行的任务和上一页的任务样子是一样的，每个批次只展示这个批次的任务

成功执行的是绿色，执行失败的是橙色，未执行的是灰色，正在重试的是黄色，执行中的是蓝色有脉冲动效有假进度条

执行到叠放任务的时候会展开分别展示进度，执行中和执行完的任务可以点击跳转到相关单个用例的详情结果页

​	-  单个用例的执行结果页有几个部分卡片:执行任务的session详情，点击可以跳转到相应的会话，展示最新的一条回显、sessionID、命名

；执行结果凭据的截图；错误报错（如有）；BUG单描述（如有）；执行时长；工具调用分别次数情况，Trace情况跳转

4、执行结果分析

需要先给出执行情况的可视化分析，包括通过和失败情况，占比，执行次数、用例个数、修复次数、平均时长、时长分布、每个用例都可以点进去看用例详情页、条状完整执行过程缩略图，

简单的结果样例如下，你还需要自己丰富

除此之外，失败的用例还需要进行任务归因，需要手选一下，失败原因和备注（可选），原因有待测系统问题（有效BUG）、工具误报、工具执行失败、用例质量四类，归因完成后可以单独导出失败的执行用例和任务json，

--- 执行结果 ---
所有 9 个测试用例已全部执行完成，结果汇总如下：

| 用例编号           | 用例名称                 | 结果     |
| ------------------ | ------------------------ | -------- |
| RequireAnalysis-01 | 测试需求分析页面正确访问 | **通过** |
| RequireAnalysis-02 | 面包屑导航路径正确       | **通过** |
| RequireAnalysis-03 | 测试流程导航显示正确     | **通过** |
| RequireAnalysis-04 | 需求来源字段显示本地选项 | **通过** |
| RequireAnalysis-05 | 需求来源切换本地/远程    | **通过** |
| RequireAnalysis-06 | 点击新增按钮打开新增界面 | **通过** |
| RequireAnalysis-07 | 新增成功                 | **通过** |
| RequireAnalysis-08 | 新增取消                 | **通过** |
| RequireAnalysis-09 | 新增界面必填项校验       | **通过** |

**RequireAnalysis-07** 还成功新增了一条测试数据 "TC-Auto-Test-Title-0720"，列表总条数从 52 增加到 53。
  --- 结束 ---
    [DEBUG] LLM judge output: '全部完成'
  [OK] 全部完成 — LLM判断: 全部完成
  Done (8m02s) 结束时间: 16:31:36

============================================================

  执行报告
============================================================

  总计: 2 个任务 | 完成: 1 | 部分完成: 0 | 中断: 1 | 跳过: 0
  总耗时: 29m52s
  平均耗时: 9m44s
\------------------------------------------------------------
    序号  任务                                         状态             耗时   session_id     开始     结束
\------------------------------------------------------------
     1  project_1 - 打开浏览器 (1/2)                    中断         11m32s 4e4c95a7...b0e6 16:01:46 16:13:22
     2  project_1 - 打开浏览器 (1/2) [已重试-中断]           中断          9m40s cc21e23c...58eb 16:13:28 16:23:24

     3  project_1 - 打开浏览器 (2/2)                    全部完成        8m02s 2eab7311...272c 16:23:27 16:31:36

============================================================

5、结果总结和上传

确认执行结果后可以选择执行重新执行失败任务还是上传结果

确认结果上传有上传BUG问题单和上传执行结果两个部分，可以分别上传，也可以都传都不传，传需要鉴权登录，传的过程可以产生sessionID

最后是结束任务或重新执行，重新执行就是新增一个从卡片2开始的东西，自动导入内容

## 原型脚本

以下是我当前使用的批量执行Demo验证使用的脚本，供参考：

"""

Serially execute claude-haha commands based on JSON config.



JSON format (array of tasks):

[

 {

  "label": "任务名称（可选，用于显示）",

  "cwd": "D:\\path\\to\\dir1",

  "prompt": "task description 1"

 },

 {

  "label": "另一个任务",

  "cwd": "D:\\path\\to\\dir1",

  "prompt": "task description 2"

 }

]

注: cwd 可以是绝对路径，也可以是相对于 config.json 所在目录的相对路径。



Usage:

  python run_claude_tasks.py <config.json>

"""



import json

import subprocess

import sys

import os

import time

import argparse

import threading

import datetime



\# Retry delay between steps

RETRY_DELAY = 3





def _find_claude_haha():

  """查找 claude/claude-haha 命令路径。优先本地安装，再查 PATH。"""

  import shutil

  \# 先检查常见本地安装路径（优先于 PATH）

  candidates = [

​    os.path.expanduser("~/.local/bin/claude-haha"),

​    os.path.expanduser("~/bin/claude-haha"),

  ]

  for c in candidates:

​    if os.path.isfile(c):

​      return c

  \# 再查 PATH

  p = shutil.which("claude-haha")

  if p:

​    return p

  print("[警告] 无法找到 claude-haha，将使用默认路径")

  return "claude-haha"



CLAUDE_HAHA = _find_claude_haha()



\# Default allowed tools list

DEFAULT_TOOLS = "Skill,Read,Write,Edit,Grep,Glob,Bash (python *),TaskCreate,TaskGet,TaskList,TaskUpdate,TaskOutput,TaskStop,test-web-execution,mcp__plugin_chrome_devtools__list_pages,mcp__plugin_chrome_devtools__navigate_page,mcp__plugin_chrome_devtools__new_page,mcp__plugin_chrome_devtools__select_page,mcp__plugin_chrome_devtools__click,mcp__plugin_chrome_devtools__hover,mcp__plugin_chrome_devtools__fill,mcp__plugin_chrome_devtools__type_text,mcp__plugin_chrome_devtools__upload_file,mcp__plugin_chrome_devtools__take_screenshot,mcp__plugin_chrome_devtools__take_snapshot,mcp__plugin_chrome_devtools__handle_dialog,mcp__plugin_chrome_devtools__list_console_messages,mcp__plugin_chrome_devtools__list_network_requests"





def build_allowed_tools(task_extra_tools=None):

  """构建 --allowedTools 参数值，合并默认工具 + 额外工具。"""

  tools = DEFAULT_TOOLS

  if task_extra_tools:

​    extra = ",".join(task_extra_tools)

​    tools = f"{tools},{extra}"

  return tools



def _get_plugin_json_path():

  """获取 plugin.json 绝对路径（延迟初始化）。"""

  return os.path.join(os.path.dirname(os.path.abspath(__file__)), "plugin.json")



\# Default command-line flags (output-format json for session_id extraction)

DEFAULT_FLAGS = f'--allowedTools "{DEFAULT_TOOLS}" --output-format json'



def build_command(prompt, allowed_tools_flags, is_resume=False, session_id=None):

  """构建执行命令。"""

  cmd = f'"{CLAUDE_HAHA}" -p "{prompt}" {allowed_tools_flags}'

  if is_resume and session_id:

​    cmd = f'"{CLAUDE_HAHA}" -p "继续" --resume "{session_id}" {allowed_tools_flags}'

  return cmd





\# Verdict categories

VERDICT_FULL = "全部完成"

VERDICT_PARTIAL = "部分完成"

VERDICT_ABORTED = "中断"



JUDGE_PROMPT = (

  "你是一个测试自动化任务分析助手。请根据下面的控制台输出来判断本次任务的状态。\n"

  "只允许返回以下三个词之一：全部完成、部分完成、中断。不要返回其他内容。\n\n"

  "判断标准：\n"

  "1. 全部完成：控制台显示已生成测试报告，且报告中所有步骤均为 PASS\n"

  "2. 部分完成：控制台显示已生成测试报告，但报告中存在步骤为 PARTIAL 或 FAIL\n"

  "3. 中断：控制台显示未生成测试报告（如执行中断、进程终止、报错退出等）\n\n"

  "以下是控制台输出：\n---\n{output}\n---\n\n请只返回一个词：全部完成、部分完成 或 中断"

)





def call_claude_judge(output_text, judge_cwd, extra_tools=None):

  """通过 claude-haha -p 调用来判断结果。"""

  if isinstance(output_text, bytes):

​    output_text = output_text.decode("utf-8", errors="replace")

  prompt = JUDGE_PROMPT.format(output=output_text[:8000]).replace("\n", "\\n")

  allowed = build_allowed_tools(extra_tools)

  cmd = f'"{CLAUDE_HAHA}" -p "{prompt}" --allowedTools "{allowed}" --output-format json'

  try:

​    result = subprocess.run(cmd, cwd=judge_cwd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)

​    judge_output = result.stdout.decode("utf-8", errors="replace")

​    \# 只解析 result 字段显示

​    try:

​      json_out = json.loads(judge_output)

​      debug_text = json_out.get("result", "")[:200]

​    except json.JSONDecodeError:

​      debug_text = judge_output[:200]

​    print(f"   [DEBUG] LLM judge output: {repr(debug_text)}")

​    if result.returncode == 0:

​      if "全部完成" in judge_output:

​        return VERDICT_FULL, "LLM判断: 全部完成"

​      elif "部分完成" in judge_output:

​        return VERDICT_PARTIAL, "LLM判断: 部分完成"

​      elif "中断" in judge_output:

​        return VERDICT_ABORTED, "LLM判断: 中断"

  except subprocess.TimeoutExpired:

​    print("   [警告] 判断超时")

  except Exception as e:

​    print(f"   [警告] 判断调用失败: {e}")

  return None, None





def parse_json_output(raw_output):

  """解析 JSON 格式的输出，返回 (session_id, result_text, raw_json)"""

  output_text = raw_output.decode("utf-8", errors="replace").strip()

  session_id = None

  result_text = ""

  raw_json = None

  try:

​    raw_json = json.loads(output_text)

​    \# 兼容 JSON 对象和 JSON 数组两种格式

​    if isinstance(raw_json, dict):

​      session_id = raw_json.get("session_id")

​      result_text = raw_json.get("result", "")

​    elif isinstance(raw_json, list):

​      for item in raw_json:

​        if isinstance(item, dict) and "result" in item:

​          session_id = item.get("session_id", "")

​          result_text = item.get("result", "")

​          break

  except json.JSONDecodeError:

​    pass

  return session_id, result_text, raw_json





def judge_task_result(console_output, prompt, judge_cwd, extra_tools=None):

  """

  根据控制台输出判断任务完成状态。



  返回元组 (verdict, details):

   \- (VERDICT_FULL, "全部完成")

   \- (VERDICT_PARTIAL, "部分完成")

   \- (VERDICT_ABORTED, "中断")

  """

  output_text = console_output.decode("utf-8", errors="replace")



  \# 空输出直接判断为中断

  if not output_text or len(output_text.strip()) < 10:

​    return VERDICT_ABORTED, "控制台输出为空"



  \# 尝试从 JSON 输出提取 result 字段作为判断依据

  _, result_text, raw_json = parse_json_output(console_output)

  judge_text = result_text if result_text else output_text

  return call_claude_judge(judge_text.encode("utf-8", errors="replace"), judge_cwd, extra_tools)





def print_timer(start, stop_event):

  """Background thread: print elapsed time every second."""

  while not stop_event.is_set():

​    elapsed = time.time() - start

​    minutes = int(elapsed // 60)

​    seconds = int(elapsed % 60)

​    print(f"\r  Elapsed: {minutes:02d}:{seconds:02d}", end="", flush=True)

​    stop_event.wait(1)





def fmt_time(total):

  """Format total seconds into human-readable string."""

  if total < 60:

​    return f"{total:.0f}s"

  minutes = int(total // 60)

  seconds = int(total % 60)

  return f"{minutes}m{seconds:02d}s"





def resolve_cwd(cwd, config_dir):

  """解析 cwd: 如果是相对路径则相对于 config.json 所在目录。"""

  if os.path.isabs(cwd):

​    return cwd

  return os.path.join(config_dir, cwd)





def expand_tasks(tasks, repeat):

  """根据 repeat 展开任务列表。每个任务支持单独设置 repeats 字段。"""

  expanded = []

  for task in tasks:

​    task_repeat = task.get("repeats", repeat)

​    for i in range(task_repeat):

​      entry = dict(task)

​      entry["_repeat_idx"] = i

​      entry["_repeat_total"] = task_repeat

​      entry["label"] = task.get("label", task["prompt"][:50])

​      entry["_task_key"] = len(expanded)  # 展开后唯一标识，每个 repeat 独立

​      expanded.append(entry)

  return expanded





def main():

  parser = argparse.ArgumentParser(description="Serially execute claude-haha commands based on JSON config.")

  parser.add_argument("config", help="JSON config file path")

  parser.add_argument("-r", "--repeat", type=int, default=1,

​            help="Repeat each task N times (default: 1). Can be overridden per-task with 'repeats' field.")

  parser.add_argument("--at", type=str, default=None,

​            help="Scheduled start time, format: HH:MM or YYYY-MM-DD HH:MM (e.g. 14:00, 2026-07-04 12:00). Will wait until that time to begin.")

  args = parser.parse_args()



  \# 等待到指定时间

  if args.at:

​    now = time.time()

​    \# 解析日期+时间或仅时间

​    if "T" in args.at:

​      \# 2026-07-03T17:34

​      target = time.mktime(time.strptime(args.at, "%Y-%m-%dT%H:%M"))

​    elif " " in args.at:

​      \# 2026-07-03 17:34

​      target = time.mktime(time.strptime(args.at, "%Y-%m-%d %H:%M"))

​    else:

​      \# 仅 HH:MM，用今天的日期

​      today = time.strftime("%Y-%m-%d")

​      target = time.mktime(time.strptime(f"{today} {args.at}", "%Y-%m-%d %H:%M"))

​      \# 如果目标时间已过，自动算明天

​      if target <= now:

​        next_day = datetime.date.today() + datetime.timedelta(days=1)

​        target = time.mktime(time.strptime(f"{next_day} {args.at}", "%Y-%m-%d %H:%M"))



​    wait_secs = target - now

​    if wait_secs > 0:

​      hours = int(wait_secs // 3600)

​      minutes = int((wait_secs % 3600) // 60)

​      print(f"定时模式: 等待到 {args.at} 开始执行（还需等待 {hours}h{minutes}m）")

​      time.sleep(wait_secs)

​    else:

​      print(f"当前时间已过 {args.at}，立即开始执行")



  config_path = args.config

  repeat = args.repeat

  config_dir = os.path.dirname(os.path.abspath(config_path))



  with open(config_path, "r", encoding="utf-8") as f:

​    data = json.load(f)



  \# 兼容旧格式: 如果 load 出来是 dict ({"dir": "prompt"})，转为新数组格式

  if isinstance(data, dict):

​    tasks = [{"cwd": k, "prompt": v} for k, v in data.items()]

  elif isinstance(data, list):

​    tasks = data

  else:

​    print(f"Error: invalid config format, expected dict or array")

​    sys.exit(1)



  \# 展开 repeat

  tasks = expand_tasks(tasks, repeat)



  total = len(tasks)

  print(f"Loaded {total} task(s) from {config_path} (repeat={repeat}x)")

  print("=" * 60)



  overall_start = time.time()

  task_durations = []

  task_stats = []

  verdict_icons = {

​    VERDICT_FULL: "[OK]",

​    VERDICT_PARTIAL: "[PARTIAL]",

​    VERDICT_ABORTED: "[ABORTED]",

  }



  for idx, task in enumerate(tasks, 1):

​    work_dir = resolve_cwd(task.get("cwd", "."), config_dir)

​    prompt = task["prompt"]

​    label = task.get("label", prompt[:50])



​    repeat_info = task.get("_repeat_idx", 0)

​    total_repeats = task.get("_repeat_total", 1)

​    task_key = task.get("_task_key", idx)  # 唯一任务标识

​    if total_repeats > 1:

​      label = f"{label} ({repeat_info+1}/{total_repeats})"

​    print(f"\n[{idx}/{total}] {label}")

​    print(f"  Dir: {work_dir}")

​    print(f"  Prompt: {prompt[:100]}{'...' if len(prompt) > 100 else ''}")

​    print(f"  开始时间: {time.strftime('%H:%M:%S')}")



​    if not os.path.isdir(work_dir):

​      print(f"  SKIP: directory does not exist: {work_dir}")

​      task_stats.append({"label": label, "work_dir": work_dir, "verdict": "SKIP", "details": "目录不存在", "duration": 0, "_task_key": task_key})

​      continue



​    \# 尝试次数：初始 + 部分完成重试1次

​    max_attempts = 2

​    session_id = None

​    verdict = None

​    details = ""

​    was_retry = False    # 是否因为部分完成/中断而重试过

​    extra_tools = task.get("extra_allowed_tools", [])



​    for attempt in range(max_attempts):

​      if attempt > 0:

​        time.sleep(RETRY_DELAY)  # 重试前等待

​        print(f"\n{'=' * 60}")

​        print(f"  [重试 #{attempt}]")

​        if was_retry:

​          print(f"  上一次判定为部分完成，正在重试...")

​        else:

​          print(f"  上一次判定为中断，正在重新执行...")

​        print(f"{'=' * 60}")



​      task_overall_start = time.time()



​      allowed = build_allowed_tools(extra_tools)

​      cmd = f'"{CLAUDE_HAHA}" -p "{prompt}" --allowedTools "{allowed}" --output-format json'



​      print(f"  Command: {cmd}")



​      \# Start timer thread

​      task_start = time.time()

​      stop_timer = threading.Event()

​      timer_thread = threading.Thread(target=print_timer, args=(task_start, stop_timer), daemon=True)

​      timer_thread.start()



​      \# Run command and capture output

​      raw_output = subprocess.run(cmd, cwd=work_dir, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)



​      \# Stop timer

​      stop_timer.set()

​      task_elapsed = time.time() - task_start



​      \# Clear timer line

​      print("\r" + " " * 40 + "\r", end="", flush=True)



​      if raw_output.returncode != 0:

​        print(f"  FAILED: exit code {raw_output.returncode}")



​      \# Parse JSON output

​      out_session_id, result_text, raw_json = parse_json_output(raw_output.stdout)

​      if out_session_id:

​        session_id = out_session_id

​        print(f"  session_id: {session_id}")



​      \# 打印 result 内容

​      if result_text:

​        print(f"  --- 执行结果 ---")

​        print(result_text)

​        print(f"  --- 结束 ---")



​      time.sleep(RETRY_DELAY)  # 执行用例后等待



​      \# Judge verdict

​      verdict, details = judge_task_result(raw_output.stdout, prompt, work_dir, extra_tools)

​      if verdict is None:

​        verdict = VERDICT_ABORTED

​        details = "判断失败（默认视为中断）"



​      icon = verdict_icons.get(verdict, "?")

​      print(f"  {icon} {verdict} — {details}")



​      \# 记录本次 attempt 统计

​      task_end = time.time()

​      print(f"  Done ({fmt_time(task_elapsed)}) 结束时间: {time.strftime('%H:%M:%S')}")

​      task_durations.append(task_elapsed)

​      attempt_start = time.strftime('%H:%M:%S', time.localtime(task_overall_start))

​      attempt_end = time.strftime('%H:%M:%S')



​      \# 判断是否需要重试

​      if verdict in (VERDICT_PARTIAL, VERDICT_ABORTED) and attempt == 0:

​        \# 首次失败，记录并准备重试

​        attempt_label = label

​        task_stats.append({"label": attempt_label, "work_dir": work_dir, "verdict": verdict, "details": details, "duration": task_elapsed, "session_id": session_id, "start_time": attempt_start, "end_time": attempt_end, "_task_key": task_key})

​        was_retry = True

​        mark = "部分完成" if verdict == VERDICT_PARTIAL else "中断"

​        print(f"  {mark}，将在下一轮重试...")

​        time.sleep(RETRY_DELAY)  # 判断后等待

​        continue

​      else:

​        \# 全部完成，或重试后仍部分/中断 -> 结束

​        if was_retry and verdict in (VERDICT_PARTIAL, VERDICT_ABORTED):

​          print(f"  [重试后] 仍为{verdict}")



​        \# 最终 label 标记

​        mark_label = label

​        if was_retry and verdict in (VERDICT_PARTIAL, VERDICT_ABORTED):

​          suffix = {"部分完成": "部分完成", "中断": "中断"}.get(verdict, verdict)

​          mark_label = f"{label} [已重试-{suffix}]"

​        elif was_retry:

​          mark_label = f"{label} [已重试-通过]"



​        attempt_label = mark_label

​        task_stats.append({"label": attempt_label, "work_dir": work_dir, "verdict": verdict, "details": details, "duration": task_elapsed, "session_id": session_id, "start_time": attempt_start, "end_time": attempt_end, "_task_key": task_key})

​        break



​    time.sleep(RETRY_DELAY)  # 下一轮任务前等待



  \# Print final execution report

  total_elapsed = time.time() - overall_start

  print("\n" + "=" * 60)

  print("  执行报告")

  print("=" * 60)



  \# 只统计最终 verdict（用最后一次 attempt 的结果）

  verdict_counts = {VERDICT_FULL: 0, VERDICT_PARTIAL: 0, VERDICT_ABORTED: 0, "SKIP": 0}

  task_keys = {}  # task_key -> verdict，后面的覆盖前面的

  for s in task_stats:

​    tk = s.get("_task_key")

​    if tk is not None:

​      task_keys[tk] = s["verdict"]

  for v in task_keys.values():

​    verdict_counts[v] = verdict_counts.get(v, 0) + 1



  print(f"  总计: {total} 个任务 | 完成: {verdict_counts[VERDICT_FULL]} | 部分完成: {verdict_counts[VERDICT_PARTIAL]} | 中断: {verdict_counts[VERDICT_ABORTED]} | 跳过: {verdict_counts['SKIP']}")

  print(f"  总耗时: {fmt_time(total_elapsed)}")

  if task_durations:

​    print(f"  平均耗时: {fmt_time(sum(task_durations) / len(task_durations))}")

  print("-" * 60)

  print(f"  {'序号':>4}  {'任务':<42} {'状态':<8} {'耗时':>8} {'session_id':>12} {'开始':>6} {'结束':>6}")

  print("-" * 60)

  for i, s in enumerate(task_stats, 1):

​    icon = verdict_icons.get(s["verdict"], "?")

​    sid = s.get("session_id", "")

​    if sid:

​      sid = sid[:8] + "..." + sid[-4:]

​    else:

​      sid = "-"

​    start_t = s.get("start_time", "")

​    end_t = s.get("end_time", "")

​    label_display = s.get("label", "")[:42]

​    print(f"  {i:4d}  {label_display:<42} {s['verdict']:<8} {fmt_time(s['duration']):>8} {sid:>12} {start_t:>6} {end_t:>6}")

  print("=" * 60)





if __name__ == "__main__":

  main()
