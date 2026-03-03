#!/usr/bin/env python3
"""세션 시작 준비 — git 싱크 + 기억 업데이트

AGENTS.md '작업 시작' 절차의 첫 단계.

사용법:
  python3 scripts/start-session.py              # git 싱크 + 기억 갭 확인 + 자동 생성
  python3 scripts/start-session.py --check-only  # 싱크 + 확인만, 생성 안 함
  python3 scripts/start-session.py --skip-sync    # git 싱크 건너뜀

절차:
  1. git pull --rebase origin main
  2. raw 세션 파일 vs nodes.json 비교 → 노드 추출 누락 세션 탐지
  3. 누락 세션 있으면 노드 추출 + 임베딩 + 네트워크 갱신
"""

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "tasks" / "conversations" / "raw"
NODES_FILE = PROJECT_ROOT / "memory" / "network" / "nodes.json"

# close-session.py에서 공통 함수 재사용
_spec = importlib.util.spec_from_file_location(
    "close_session", str(PROJECT_ROOT / "scripts" / "close-session.py")
)
_cs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_cs)


# ── git 싱크 ──

def git_sync() -> bool:
    """메인 브랜치 최신 싱크. 성공 여부 반환."""
    print("── 1. Git 싱크 ──")

    # 커밋되지 않은 변경 확인
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True
    )
    if status.stdout.strip():
        print("  uncommitted 변경 있음 — stash 후 pull")
        subprocess.run(["git", "stash"], cwd=str(PROJECT_ROOT), capture_output=True)
        stashed = True
    else:
        stashed = False

    result = subprocess.run(
        ["git", "pull", "--rebase", "origin", "main"],
        cwd=str(PROJECT_ROOT), capture_output=True, text=True
    )

    if stashed:
        subprocess.run(["git", "stash", "pop"], cwd=str(PROJECT_ROOT), capture_output=True)

    if result.returncode != 0:
        print(f"  git pull 실패: {result.stderr.strip()}")
        print("  (계속 진행)")
        return False

    output = result.stdout.strip()
    print(f"  {output}")
    return True


# ── 기억 갭 탐지 ──

def find_unprocessed_sessions() -> dict[str, Path]:
    """raw 세션 파일 중 nodes.json에 노드가 없는 세션 찾기."""
    # raw 파일에서 세션 이름 추출 (파일명 = 세션 이름)
    raw_sessions = {}
    for f in sorted(RAW_DIR.glob("*.jsonl")):
        if f.name.startswith("."):
            continue
        raw_sessions[f.stem] = f

    # nodes.json에서 세션 목록
    nodes = json.load(open(NODES_FILE))
    node_sessions = set(n.get("session", "") for n in nodes)

    # 차집합: raw에는 있는데 nodes에는 없는 세션
    unprocessed = {}
    for name, path in raw_sessions.items():
        if name not in node_sessions:
            unprocessed[name] = path

    return unprocessed


# ── raw 파일용 대화 추출 ──

def extract_conversation_from_raw(filepath: Path, max_chars: int = 15000) -> str:
    """경량 raw JSONL에서 대화 텍스트 추출.

    close-session.py의 export_raw가 생성한 포맷:
      {"type": "user", "role": "user", "content": "..."}
    원본 JSONL과 달리 message 래퍼가 없다.
    """
    lines = []
    total_chars = 0

    with open(filepath, encoding="utf-8") as f:
        for raw_line in f:
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

            msg_type = record.get("type")
            content = record.get("content", "")

            if msg_type == "user":
                if isinstance(content, str) and content.strip():
                    block = f"\n[사용자] {content.strip()}"
                    lines.append(block)
                    total_chars += len(block)

            elif msg_type == "assistant":
                texts = []
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for item in content:
                        if isinstance(item, dict) and item.get("type") == "text":
                            texts.append(item.get("text", ""))
                full_text = "\n".join(t for t in texts if t.strip())
                if full_text:
                    if len(full_text) > 1500:
                        full_text = full_text[:1500] + "\n... (생략)"
                    block = f"\n[AI] {full_text}"
                    lines.append(block)
                    total_chars += len(block)

            if max_chars > 0 and total_chars >= max_chars:
                break

    return "\n".join(lines)


# ── 노드 추출 (세션 이름을 그대로 사용) ──

def extract_nodes_for_session(conversation: str, session_name: str) -> list[dict]:
    """raw 세션에서 노드 추출. close-session과 달리 기존 세션 이름을 그대로 사용."""
    prompt = _cs.NODE_EXTRACT_PROMPT.format(
        date_session=session_name,
        conversation=conversation,
    )
    raw = _cs.call_codex(prompt, timeout=180)
    if not raw:
        return []

    try:
        match = re.search(r'\[.*\]', raw, re.DOTALL)
        if match:
            nodes = json.loads(match.group())
            return [n for n in nodes if isinstance(n, dict) and "content" in n]
    except (json.JSONDecodeError, Exception):
        pass
    return []


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="세션 시작 준비")
    parser.add_argument("--check-only", action="store_true", help="갭 확인만, 생성 안 함")
    parser.add_argument("--skip-sync", action="store_true", help="git 싱크 건너뜀")
    args = parser.parse_args()

    # 1. Git 싱크
    if not args.skip_sync:
        git_sync()
    else:
        print("── 1. Git 싱크 (건너뜀) ──")

    # 2. 기억 갭 확인
    print("\n── 2. 기억 업데이트 확인 ──")
    unprocessed = find_unprocessed_sessions()

    if not unprocessed:
        print("  모든 세션 처리 완료. 추가 작업 없음.")
        return

    print(f"  미처리 세션 {len(unprocessed)}건:")
    for name in sorted(unprocessed.keys()):
        print(f"    - {name}")

    if args.check_only:
        print("\n  (--check-only: 생성 건너뜀)")
        return

    # 3. 기억 생성
    print("\n── 3. 기억 생성 ──")
    _cs.load_env()

    all_new_nodes = []
    for name, path in sorted(unprocessed.items()):
        print(f"\n  [{name}]")
        conversation = extract_conversation_from_raw(path, max_chars=15000)
        if not conversation.strip():
            print(f"    대화 내용 비어있음, 건너뜀")
            continue

        print(f"    대화: {len(conversation)}자")
        print(f"    codex 노드 추출 중...")
        nodes = extract_nodes_for_session(conversation, name)

        facts = sum(1 for n in nodes if n.get("type") == "fact")
        intents = sum(1 for n in nodes if n.get("type") == "intention")
        print(f"    추출: {len(nodes)}개 (fact {facts}, intention {intents})")
        all_new_nodes.extend(nodes)

    if not all_new_nodes:
        print("\n  추출된 노드 없음.")
        return

    # 네트워크 갱신
    print(f"\n  노드 추가: {len(all_new_nodes)}개...")
    added = _cs.add_nodes_to_network(all_new_nodes)

    total_nodes = len(json.load(open(NODES_FILE)))
    print(f"  전체 노드: {total_nodes}개")

    print("  임베딩 계산...")
    _cs.compute_embeddings_incremental(added)

    print("  네트워크 재구축 (knn_k12)...")
    edge_count = _cs.rebuild_network()

    print(f"\n  [완료] +{added}노드, {edge_count}엣지")


if __name__ == "__main__":
    main()
