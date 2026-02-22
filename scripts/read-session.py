#!/usr/bin/env python3
"""세션 JSONL 원시 데이터 조회 스크립트

사용법:
  python scripts/read-session.py <session-id> [--from HH:MM] [--to HH:MM] [--role user|assistant] [--no-tools]

예시:
  python scripts/read-session.py 3b2357f1 --from 01:46 --to 03:30
  python scripts/read-session.py 3b2357f1 --role user
  python scripts/read-session.py 3b2357f1 --no-tools

출력: JSONL (각 줄이 JSON 객체, 파이프라인으로 jq 등과 연결 가능)
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"


def find_session_file(session_id: str) -> Path | None:
    for jsonl in CLAUDE_PROJECTS_DIR.rglob("*.jsonl"):
        if session_id in jsonl.stem:
            return jsonl
    return None


def parse_time(t: str, date_str: str = "2026-02-22") -> datetime:
    return datetime.fromisoformat(f"{date_str}T{t}:00")


def filter_messages(filepath: Path, args) -> list[dict]:
    results = []
    with open(filepath) as f:
        for line in f:
            record = json.loads(line)

            # 타임스탬프 필터
            ts = record.get("timestamp")
            if not ts:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))

            if args.from_time:
                date_str = dt.strftime("%Y-%m-%d")
                if dt < parse_time(args.from_time, date_str).replace(tzinfo=dt.tzinfo):
                    continue
            if args.to_time:
                date_str = dt.strftime("%Y-%m-%d")
                if dt > parse_time(args.to_time, date_str).replace(tzinfo=dt.tzinfo):
                    continue

            # 메시지가 아닌 레코드 제외 (file-history-snapshot, progress 등)
            rec_type = record.get("type")
            if rec_type not in ("user", "assistant"):
                continue

            # 메타 메시지 제외
            if record.get("isMeta"):
                continue

            # role 필터
            msg = record.get("message", {})
            role = msg.get("role", rec_type)
            if args.role and role != args.role:
                continue

            # 도구 호출 제외 옵션
            if args.no_tools:
                content = msg.get("content", "")
                if isinstance(content, list):
                    has_text = any(
                        c.get("type") == "text" for c in content if isinstance(c, dict)
                    )
                    if not has_text:
                        continue

            results.append({
                "timestamp": ts,
                "role": role,
                "content": msg.get("content", ""),
            })

    return results


def main():
    parser = argparse.ArgumentParser(description="세션 JSONL 원시 데이터 조회")
    parser.add_argument("session_id", help="세션 ID (부분 매칭 가능)")
    parser.add_argument("--from", dest="from_time", help="시작 시간 (HH:MM)")
    parser.add_argument("--to", dest="to_time", help="종료 시간 (HH:MM)")
    parser.add_argument("--role", choices=["user", "assistant"], help="역할 필터")
    parser.add_argument("--no-tools", action="store_true", help="도구 호출 메시지 제외")
    args = parser.parse_args()

    filepath = find_session_file(args.session_id)
    if not filepath:
        print(f"세션 '{args.session_id}' 파일을 찾을 수 없음", file=sys.stderr)
        sys.exit(1)

    messages = filter_messages(filepath, args)
    for msg in messages:
        print(json.dumps(msg, ensure_ascii=False))


if __name__ == "__main__":
    main()
