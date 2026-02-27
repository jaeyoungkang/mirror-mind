#!/bin/bash
# 프롬프트 입력 시 기억 활성화 → 컨텍스트 주입
# UserPromptSubmit 훅: LLM에 전달되기 전에 관련 기억을 자동 주입

set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
ACTIVATE="$PROJECT_DIR/memory/.venv/bin/python3"
ACTIVATE_SCRIPT="$PROJECT_DIR/scripts/activate.py"
TRANSCRIPT_TAIL_LINES=20

# stdin에서 JSON 읽기
INPUT=$(cat)
PROMPT=$(echo "$INPUT" | jq -r '.prompt // ""')
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')

# 짧은 프롬프트는 스킵 (10자 미만)
if [ "${#PROMPT}" -lt 10 ]; then
  exit 0
fi

# 쿼리 구성: 최근 대화 맥락 + 현재 프롬프트
QUERY="$PROMPT"

# transcript가 있으면 최근 대화에서 assistant 메시지를 추출해 맥락 보강
if [ -n "$TRANSCRIPT_PATH" ] && [ -f "$TRANSCRIPT_PATH" ]; then
  # 최근 몇 줄에서 assistant 메시지 텍스트 추출 (간략하게)
  RECENT_CONTEXT=$(tail -n "$TRANSCRIPT_TAIL_LINES" "$TRANSCRIPT_PATH" 2>/dev/null \
    | jq -r 'select(.role == "assistant") | .message.content[]? | select(.type == "text") | .text' 2>/dev/null \
    | tail -c 200 || true)

  if [ -n "$RECENT_CONTEXT" ]; then
    QUERY="${RECENT_CONTEXT} ${PROMPT}"
  fi
fi

# 기억 활성화 실행
RESULT=$("$ACTIVATE" "$ACTIVATE_SCRIPT" --query "$QUERY" --top 10 2>/dev/null || true)

if [ -n "$RESULT" ]; then
  echo "<memory-context>"
  echo "$RESULT"
  echo "</memory-context>"
fi

exit 0
