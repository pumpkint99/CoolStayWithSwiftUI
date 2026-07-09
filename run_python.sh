#!/bin/bash
#
# main.py를 백그라운드로 실행하고 로그를 .log 파일로 저장하는 스크립트
#
# 사용법:
#   ./run_main.sh          # 실행
#   ./run_main.sh stop     # 종료
#   ./run_main.sh status   # 실행 상태 확인
#

# ===== 설정 (필요에 맞게 수정) =====
APP_NAME="main"
PYTHON_BIN="python3"
SCRIPT_PATH="./main.py"

LOG_DIR="./logs"
PID_FILE="./${APP_NAME}.pid"
# 실행 시각을 파일명에 포함해서 매 실행마다 새 로그 파일 생성
LOG_FILE="${LOG_DIR}/${APP_NAME}_$(date +%Y%m%d_%H%M%S).log"
# ===================================

mkdir -p "$LOG_DIR"

start() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "이미 실행 중입니다. (PID: $(cat "$PID_FILE"))"
        exit 1
    fi

    echo "백그라운드로 실행합니다..."
    nohup "$PYTHON_BIN" -u "$SCRIPT_PATH" >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    echo "실행 완료 (PID: $(cat "$PID_FILE"))"
    echo "로그 파일: $LOG_FILE"
}

stop() {
    if [ ! -f "$PID_FILE" ]; then
        echo "PID 파일이 없습니다. 실행 중인 프로세스가 없는 것 같습니다."
        exit 1
    fi

    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "프로세스(PID: $PID)를 종료했습니다."
        rm -f "$PID_FILE"
    else
        echo "PID $PID 는 이미 종료된 상태입니다."
        rm -f "$PID_FILE"
    fi
}

status() {
    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo "실행 중입니다. (PID: $(cat "$PID_FILE"))"
    else
        echo "실행 중이 아닙니다."
    fi
}

case "$1" in
    stop)
        stop
        ;;
    status)
        status
        ;;
    *)
        start
        ;;
esac