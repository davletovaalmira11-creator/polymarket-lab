#!/data/data/com.termux/files/usr/bin/bash
# Unified control script for web_dashboard.py
# Usage: ./manage_dashboard.sh [start|stop|status]

PORT=8080
SCRIPT_PATH="/data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/web_dashboard.py"
PID_FILE="/data/data/com.termux/files/home/AI_WORKSPACE/polymarket_lab/dashboard.pid"

start() {
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
        echo "Dashboard is already running (PID: $(cat "$PID_FILE"))."
    else
        nohup python3 "$SCRIPT_PATH" > dashboard.log 2>&1 &
        echo $! > "$PID_FILE"
        echo "Dashboard started (PID: $!)."
    fi
}

stop() {
    if [ -f "$PID_FILE" ]; then
        kill $(cat "$PID_FILE")
        rm "$PID_FILE"
        echo "Dashboard stopped."
    else
        echo "Dashboard is not running."
    fi
}

status() {
    if [ -f "$PID_FILE" ] && ps -p $(cat "$PID_FILE") > /dev/null; then
        echo "Dashboard is running (PID: $(cat "$PID_FILE"))."
    else
        echo "Dashboard is stopped."
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    *) echo "Usage: $0 {start|stop|status}" ;;
esac
