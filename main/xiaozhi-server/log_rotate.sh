#!/bin/bash

# 日志轮转脚本
# 将非今天的日志移到 app_other.log

LOG_FILE="./app.log"
OTHER_LOG_FILE="./app_other.log"
TODAY=$(date +%y%m%d)

if [ ! -f "$LOG_FILE" ]; then
    echo "日志文件不存在: $LOG_FILE"
    exit 0
fi

# 提取非今天的日志
grep -v "^${TODAY} " "$LOG_FILE" > /tmp/app_other.tmp 2>/dev/null

# 提取今天的日志
grep "^${TODAY} " "$LOG_FILE" > /tmp/app_today.tmp 2>/dev/null

# 如果有非今天的日志，追加到 app_other.log
if [ -s /tmp/app_other.tmp ]; then
    cat /tmp/app_other.tmp >> "$OTHER_LOG_FILE"
    echo "已将 $(wc -l < /tmp/app_other.tmp) 行历史日志移到 $OTHER_LOG_FILE"
fi

# 用今天的日志替换原文件
if [ -s /tmp/app_today.tmp ]; then
    mv /tmp/app_today.tmp "$LOG_FILE"
else
    # 如果没有今天的日志，创建空文件
    > "$LOG_FILE"
fi

# 清理临时文件
rm -f /tmp/app_other.tmp /tmp/app_today.tmp

echo "日志轮转完成"
