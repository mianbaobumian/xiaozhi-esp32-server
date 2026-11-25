#!/bin/bash

# ------------------ 配置区 ------------------
APP_NAME="xiaozhi-app"
WORK_DIR="/home/dapao/xiaozhi/xiaozhi-esp32-server/main/xiaozhi-server/"
PYTHON="/home/dapao/miniconda3/envs/xiaozhi/bin/python"
APP_SCRIPT="app.py"
PID_FILE="app.pid"
LOG_FILE="./app.log"
# -------------------------------------------

cd "$WORK_DIR" || { echo "无法进入工作目录: $WORK_DIR"; exit 1; }

start() {
    # 检查是否已有进程在运行（精确匹配工作目录）
    EXISTING_PID=$(pgrep -f "$WORK_DIR$APP_SCRIPT" | head -1)
    if [ -z "$EXISTING_PID" ]; then
        EXISTING_PID=$(pgrep -f "$PYTHON.*$WORK_DIR$APP_SCRIPT" | head -1)
    fi
    if [ -n "$EXISTING_PID" ]; then
        echo "应用已在运行，PID: $EXISTING_PID"
        exit 1
    fi

    # 日志轮转：将非今天的日志移到 app_other.log
    if [ -f "./log_rotate.sh" ]; then
        ./log_rotate.sh
    fi

    echo "正在启动 $APP_NAME..."
    nohup "$PYTHON" "$APP_SCRIPT" >> "$LOG_FILE" 2>&1 &
    PID=$!
    echo "$PID" > "$PID_FILE"
    echo "$APP_NAME 启动成功，PID: $PID"
}

stop() {
    echo "正在停止 $APP_NAME..."

    # 方法1: 通过 PID 文件停止
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if kill -0 "$PID" 2>/dev/null; then
            echo "通过 PID 文件停止进程: $PID"
            kill "$PID"
            sleep 2
            # 如果还在运行，强制杀死
            if kill -0 "$PID" 2>/dev/null; then
                echo "进程未响应，强制杀死..."
                kill -9 "$PID"
            fi
        fi
        rm -f "$PID_FILE"
    fi

    # 方法2: 通过进程名查找并停止（精确匹配工作目录）
    PIDS=$(pgrep -f "$WORK_DIR$APP_SCRIPT")
    if [ -z "$PIDS" ]; then
        PIDS=$(pgrep -f "$PYTHON.*$WORK_DIR$APP_SCRIPT")
    fi
    if [ -n "$PIDS" ]; then
        echo "发现残留进程，正在清理: $PIDS"
        echo "$PIDS" | xargs kill -9 2>/dev/null
    fi

    echo "$APP_NAME 已停止"
}

status() {
    PID=$(pgrep -f "$WORK_DIR$APP_SCRIPT" | head -1)
    if [ -z "$PID" ]; then
        PID=$(pgrep -f "$PYTHON.*$WORK_DIR$APP_SCRIPT" | head -1)
    fi
    if [ -n "$PID" ]; then
        echo "$APP_NAME 正在运行，PID: $PID"
    else
        echo "$APP_NAME 未运行"
    fi
}

case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        stop
        sleep 2
        start
        ;;
    status)
        status
        ;;
    *)
        echo "用法: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
