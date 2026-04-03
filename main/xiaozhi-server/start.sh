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
    EXISTING_PID=$(pgrep -f "app.py.*xiaozhi")
    if [ -n "$EXISTING_PID" ]; then
        echo "应用已在运行，PID: $EXISTING_PID"
        exit 1
    fi

    echo "正在启动 $APP_NAME..."
    nohup "$PYTHON" "$APP_SCRIPT" > "$LOG_FILE" 2>&1 &
    echo "$APP_NAME 启动成功"
}

stop() {
    echo "正在停止 $APP_NAME..."
    pkill -f "app.py.*xiaozhi"
    rm -f "$PID_FILE"
    echo "$APP_NAME 已停止"
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
    *)
        echo "用法: $0 {start|stop|restart}"
        exit 1
        ;;
esac
