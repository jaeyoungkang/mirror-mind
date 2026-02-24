#!/usr/bin/env python3
"""raw JSONL에서 사람이 읽을 수 있는 대화 텍스트를 추출한다.

사용법:
  python3 memory/scripts/extract_text.py tasks/conversations/raw/2026-02-22-세션1.jsonl
  python3 memory/scripts/extract_text.py tasks/conversations/raw/2026-02-22-세션1.jsonl --max-chars 8000
"""

import json
import sys
import argparse
from pathlib import Path


def extract_messages(filepath: Path, max_chars: int = 0) -> str:
    lines = []
    total_chars = 0

    with open(filepath, encoding="utf-8") as f:
        for raw_line in f:
            record = json.loads(raw_line)
            msg_type = record.get("type")

            if msg_type == "user":
                content = record.get("message", {}).get("content", "")
                if isinstance(content, str) and content.strip():
                    block = f"\n[사용자] {content.strip()}"
                    lines.append(block)
                    total_chars += len(block)

            elif msg_type == "assistant":
                msg = record.get("message", {})
                content = msg.get("content", "")
                texts = []
                tool_calls = []

                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                texts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                tool_name = block.get("name", "?")
                                tool_input = block.get("input", {})
                                # 간략화
                                if isinstance(tool_input, dict):
                                    summary_parts = []
                                    for k, v in tool_input.items():
                                        v_str = str(v)
                                        if len(v_str) > 80:
                                            v_str = v_str[:80] + "..."
                                        summary_parts.append(f"{k}={v_str}")
                                    tool_calls.append(f"  [도구: {tool_name}({', '.join(summary_parts[:3])})]")
                                else:
                                    tool_calls.append(f"  [도구: {tool_name}]")

                full_text = "\n".join(t for t in texts if t.strip())
                if full_text or tool_calls:
                    block_parts = []
                    if full_text:
                        # 너무 긴 텍스트 요약
                        if len(full_text) > 2000:
                            full_text = full_text[:2000] + "\n  ... (이하 생략)"
                        block_parts.append(f"\n[AI] {full_text}")
                    for tc in tool_calls[:5]:  # 도구 호출은 최대 5개
                        block_parts.append(tc)

                    block = "\n".join(block_parts)
                    lines.append(block)
                    total_chars += len(block)

            if max_chars > 0 and total_chars >= max_chars:
                lines.append(f"\n--- {max_chars}자 제한으로 여기서 중단 ---")
                break

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="raw JSONL → 대화 텍스트 추출")
    parser.add_argument("file", help="JSONL 파일 경로")
    parser.add_argument("--max-chars", type=int, default=0, help="최대 문자 수 (0=무제한)")
    args = parser.parse_args()

    filepath = Path(args.file)
    if not filepath.exists():
        print(f"파일 없음: {filepath}", file=sys.stderr)
        sys.exit(1)

    print(f"=== {filepath.stem} ===")
    print(extract_messages(filepath, args.max_chars))


if __name__ == "__main__":
    main()
