#!/usr/bin/env python3
"""输出当前时间戳字符串，格式 YYYYMMDD_HHmmss。

用法:
    python get_timestamp.py

输出:
    标准输出打印时间戳，如 20260623_143000
"""

import datetime
import sys

if __name__ == "__main__":
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    print(ts)
