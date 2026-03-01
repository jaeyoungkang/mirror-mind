#!/bin/bash
# 메타에이전트: 매 프롬프트마다 원칙 준수 점검
# UserPromptSubmit 훅: LLM이 최근 대화를 평가하고 위반 시 피드백 주입

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PYTHON="$PROJECT_DIR/memory/.venv/bin/python3"
CHECK_SCRIPT="$PROJECT_DIR/scripts/check.py"

# stdin에서 hook JSON 읽기 → check.py --prompt-mode로 전달
INPUT=$(cat)

# check.py가 없으면 스킵
if [ ! -f "$CHECK_SCRIPT" ]; then
  exit 0
fi

# prompt-mode 실행 (stdin으로 hook JSON 전달)
echo "$INPUT" | "$PYTHON" "$CHECK_SCRIPT" --prompt-mode 2>/dev/null || true

exit 0
