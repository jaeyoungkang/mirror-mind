#!/bin/bash
# SessionStart 훅: 메타에이전트 백그라운드 감시 시작
# 5분 간격으로 원칙 준수 점검

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$PROJECT_DIR/memory/.venv/bin/python3"
CHECK_SCRIPT="$PROJECT_DIR/scripts/check.py"

# 이미 실행 중인 check.py가 있으면 스킵
if pgrep -f "check.py --watch" > /dev/null 2>&1; then
  exit 0
fi

# 백그라운드 실행 (nohup으로 세션과 분리)
nohup "$PYTHON" "$CHECK_SCRIPT" --watch --interval 300 > /dev/null 2>&1 &

exit 0
