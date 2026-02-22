#!/usr/bin/env python3
"""세션 원시 데이터를 깃 공유용 경량 JSONL로 변환

사용법:
  python scripts/export-session.py <session-id> -o <output-path>

예시:
  python scripts/export-session.py 3b2357f1 -o tasks/conversations/raw/2026-02-22-세션1.jsonl

변환 규칙:
  - user/assistant/system 레코드만 추출 (progress, file-history-snapshot 등 제외)
  - tool_use: 도구명 + 입력값(300자 제한) 보존
  - tool_result: 결과 미리보기(200자 제한) 보존
  - 대화 흐름과 의사결정 맥락 복원에 충분한 수준
"""

import json
import sys
import argparse
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

TRUNCATE_INPUT = 300
TRUNCATE_RESULT = 200


def find_session_file(session_id: str) -> Path | None:
    for jsonl in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        if session_id in jsonl.stem:
            return jsonl
    return None


def truncate(v, limit):
    s = str(v)
    if len(s) > limit:
        return s[:limit] + "...[truncated]"
    return v


def compact_input(inp):
    if not isinstance(inp, dict):
        return truncate(inp, TRUNCATE_INPUT)
    return {k: truncate(v, TRUNCATE_INPUT) for k, v in inp.items()}


def compact_content(content):
    if not isinstance(content, list):
        return content
    compacted = []
    for block in content:
        if not isinstance(block, dict):
            compacted.append(block)
            continue
        t = block.get("type")
        if t == "text":
            compacted.append(block)
        elif t == "tool_use":
            compacted.append({
                "type": "tool_use",
                "name": block.get("name"),
                "input": compact_input(block.get("input", {})),
            })
        elif t == "tool_result":
            raw = block.get("content", "")
            if isinstance(raw, list):
                raw = " ".join(
                    str(c.get("text", "")) for c in raw if isinstance(c, dict)
                )
            preview = str(raw)[:TRUNCATE_RESULT]
            if len(str(raw)) > TRUNCATE_RESULT:
                preview += "...[truncated]"
            compacted.append({
                "type": "tool_result",
                "tool_use_id": block.get("tool_use_id"),
                "content_preview": preview,
            })
        else:
            compacted.append(block)
    return compacted


def export(filepath: Path, output: Path):
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(filepath) as fin, open(output, "w") as fout:
        for line in fin:
            record = json.loads(line)
            if record.get("type") not in ("user", "assistant", "system"):
                continue
            msg = record.get("message", {})
            compacted = {
                "timestamp": record.get("timestamp"),
                "type": record.get("type"),
                "role": msg.get("role", record.get("type")),
                "content": compact_content(msg.get("content", "")),
            }
            fout.write(json.dumps(compacted, ensure_ascii=False) + "\n")
            count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="세션 원시 데이터 → 경량 JSONL 변환")
    parser.add_argument("session_id", help="세션 ID (부분 매칭 가능)")
    parser.add_argument("-o", "--output", required=True, help="출력 경로")
    args = parser.parse_args()

    filepath = find_session_file(args.session_id)
    if not filepath:
        print(f"세션 '{args.session_id}' 파일을 찾을 수 없음", file=sys.stderr)
        sys.exit(1)

    output = Path(args.output)
    count = export(filepath, output)
    size_kb = output.stat().st_size / 1024
    print(f"{count}개 레코드 → {output} ({size_kb:.0f}KB)")


if __name__ == "__main__":
    main()
