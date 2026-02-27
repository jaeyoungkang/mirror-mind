#!/usr/bin/env python3
"""세션 종료 자동화 (v3 네트워크 기반)

AGENTS.md '작업 종료' 트리거 절차를 스크립트로 수행한다.

사용법:
  python3 scripts/close-session.py                     # 전체 (raw 저장 + 노드 추출 + 네트워크 갱신)
  python3 scripts/close-session.py --raw-only           # raw 저장만
  python3 scripts/close-session.py --no-llm             # codex 없이 raw 저장만
  python3 scripts/close-session.py --name 세션20        # 세션 이름 직접 지정
  python3 scripts/close-session.py --dry-run            # 파일 미수정, stdout 출력만
  python3 scripts/close-session.py --commit             # 완료 후 자동 커밋

절차:
  1. 현재 세션 JSONL → tasks/conversations/raw/ 경량 내보내기
  2. 대화 텍스트 추출
  3. codex exec로 fact/intention 노드 추출
  4. nodes.json에 추가 + 임베딩 계산 + knn_k12 네트워크 재구축
  5. (--commit) git add + commit

주의: projects.md 업데이트는 수동. 스크립트가 마지막에 알려준다.
"""

import json
import sys
import re
import subprocess
import tempfile
import argparse
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"
PROJECT_KEY = "-Users-jaeyoungkang-mirror-mind"

CONV_DIR = PROJECT_ROOT / "tasks" / "conversations"
RAW_DIR = CONV_DIR / "raw"
SESSION_MAP_FILE = RAW_DIR / ".session-map.json"

NETWORK_DIR = PROJECT_ROOT / "memory" / "network"
NODES_FILE = NETWORK_DIR / "nodes.json"
EMBEDDINGS_FILE = NETWORK_DIR / "embeddings.json"
GRAPH_FILE = NETWORK_DIR / "graph.json"

TRUNCATE_INPUT = 300
TRUNCATE_RESULT = 200

K = 12
WEIGHT_FLOOR = 0.3


# ── 세션 탐색 + 중복 방지 ──

def find_current_session() -> Path | None:
    """가장 최근 수정된 JSONL = 현재 세션"""
    project_dir = CLAUDE_PROJECTS_DIR / PROJECT_KEY
    jsonls = list(project_dir.glob("*.jsonl"))
    if not jsonls:
        return None
    return max(jsonls, key=lambda p: p.stat().st_mtime)


def load_session_map() -> dict:
    if SESSION_MAP_FILE.exists():
        return json.loads(SESSION_MAP_FILE.read_text())
    return {}


def save_session_map(mapping: dict):
    SESSION_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    SESSION_MAP_FILE.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n"
    )


def get_session_uuid(session_jsonl: Path) -> str:
    return session_jsonl.stem


def determine_session_name() -> str:
    all_sessions = list(RAW_DIR.glob("*-세션*.jsonl"))
    max_num = 0
    for f in all_sessions:
        m = re.search(r'세션(\d+)', f.name)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"세션{max_num + 1}"


def check_already_closed(session_jsonl: Path) -> str | None:
    uuid = get_session_uuid(session_jsonl)
    mapping = load_session_map()
    return mapping.get(uuid)


# ── 경량 내보내기 ──

def _truncate(v, limit):
    s = str(v)
    return s[:limit] + "...[truncated]" if len(s) > limit else v


def _compact_input(inp):
    if not isinstance(inp, dict):
        return _truncate(inp, TRUNCATE_INPUT)
    return {k: _truncate(v, TRUNCATE_INPUT) for k, v in inp.items()}


def _compact_content(content):
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
                "input": _compact_input(block.get("input", {})),
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


def export_raw(session_jsonl: Path, session_name: str) -> tuple[Path, int]:
    today = date.today().isoformat()
    dest = RAW_DIR / f"{today}-{session_name}.jsonl"
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    with open(session_jsonl) as fin, open(dest, "w") as fout:
        for line in fin:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if record.get("type") not in ("user", "assistant", "system"):
                continue
            msg = record.get("message", {})
            compacted = {
                "timestamp": record.get("timestamp"),
                "type": record.get("type"),
                "role": msg.get("role", record.get("type")),
                "content": _compact_content(msg.get("content", "")),
            }
            fout.write(json.dumps(compacted, ensure_ascii=False) + "\n")
            count += 1

    return dest, count


# ── 대화 추출 ──

def extract_conversation(filepath: Path, max_chars: int = 15000) -> str:
    lines = []
    total_chars = 0

    with open(filepath, encoding="utf-8") as f:
        for raw_line in f:
            try:
                record = json.loads(raw_line)
            except json.JSONDecodeError:
                continue

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
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    for block in content:
                        if isinstance(block, dict) and block.get("type") == "text":
                            texts.append(block.get("text", ""))
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


# ── codex 호출 ──

def call_codex(prompt: str, timeout: int = 180) -> str:
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        output_path = f.name

    cmd = [
        "codex", "exec",
        "--sandbox", "read-only",
        "--ephemeral",
        "--skip-git-repo-check",
        "-o", output_path,
        "-",
    ]
    try:
        subprocess.run(
            cmd, input=prompt,
            capture_output=True, text=True, timeout=timeout,
            cwd=str(PROJECT_ROOT),
        )
        result_path = Path(output_path)
        if result_path.exists():
            return result_path.read_text().strip()
        return ""
    except subprocess.TimeoutExpired:
        print("codex 타임아웃", file=sys.stderr)
        return ""
    except Exception as e:
        print(f"codex 호출 실패: {e}", file=sys.stderr)
        return ""
    finally:
        Path(output_path).unlink(missing_ok=True)


# ── 노드 추출 ──

NODE_EXTRACT_PROMPT = """너는 mirror-mind 프로젝트의 기억 노드 추출 담당이다.
아래 대화를 읽고 fact/intention 노드를 추출하라.

## 세션 정보
- 세션: {date_session}

## 대화 내용
{conversation}

## 추출 규칙
- AI(브로콜리) 1인칭 시점으로 작성: "~했다", "~이다"
- 타입 2가지만: fact (사실), intention (의도/판단)
- 하나의 content에 하나의 사실 또는 의도만
- context_hint: 짧은 맥락 힌트 (예: "기억 시스템 설계", "속도 개선")
- 사소한 것은 제외. 의사결정, 설계, 발견, 교훈 등 의미 있는 내용만
- 30~60개 추출

## 출력 형식
JSON 배열만 출력하라. JSON 외 텍스트 금지.

[
  {{"content": "...", "type": "fact", "session": "{date_session}", "context_hint": "..."}},
  ...
]"""


def extract_nodes(conversation: str, session_name: str) -> list[dict]:
    today = date.today().isoformat()
    date_session = f"{today}-{session_name}"

    prompt = NODE_EXTRACT_PROMPT.format(
        date_session=date_session,
        conversation=conversation,
    )

    raw = call_codex(prompt, timeout=180)
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


# ── 네트워크 갱신 ──

def load_env():
    """프로젝트 .env에서 환경변수 로드"""
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        import os
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def add_nodes_to_network(new_nodes: list[dict]) -> int:
    """새 노드를 nodes.json에 추가. 추가된 개수 반환."""
    nodes = json.load(open(NODES_FILE))
    next_id = len(nodes)

    for n in new_nodes:
        n["id"] = f"n{next_id:04d}"
        next_id += 1

    nodes.extend(new_nodes)
    with open(NODES_FILE, "w") as f:
        json.dump(nodes, f, ensure_ascii=False, indent=2)

    return len(new_nodes)


def compute_embeddings_incremental(new_count: int):
    """새 노드만 임베딩 계산하여 기존에 추가."""
    import numpy as np
    from openai import OpenAI

    nodes = json.load(open(NODES_FILE))
    old_embs = np.array(json.load(open(EMBEDDINGS_FILE)))

    client = OpenAI()
    new_texts = [n["content"] for n in nodes[old_embs.shape[0]:]]

    BATCH = 200
    new_embs = []
    for i in range(0, len(new_texts), BATCH):
        batch = new_texts[i:i + BATCH]
        resp = client.embeddings.create(model="text-embedding-3-small", input=batch)
        new_embs.extend([d.embedding for d in resp.data])

    all_embs = np.vstack([old_embs, np.array(new_embs)])
    with open(EMBEDDINGS_FILE, "w") as f:
        json.dump(all_embs.tolist(), f)

    return all_embs.shape[0]


def rebuild_network():
    """knn_k12 네트워크 전체 재구축."""
    import numpy as np

    nodes = json.load(open(NODES_FILE))
    embs = np.array(json.load(open(EMBEDDINGS_FILE)))

    # 코사인 유사도
    norms = np.linalg.norm(embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = embs / norms
    sim_matrix = normed @ normed.T

    # knn_k12 엣지
    edges = []
    edge_set = set()

    for i in range(len(nodes)):
        sims = sim_matrix[i].copy()
        sims[i] = -1
        topk = np.argsort(sims)[-K:][::-1]

        for j in topk:
            w = float(sims[j])
            if w < WEIGHT_FLOOR:
                continue

            src = nodes[i]["id"]
            tgt = nodes[int(j)]["id"]
            key = tuple(sorted([src, tgt]))

            if key in edge_set:
                for e in edges:
                    if tuple(sorted([e["source"], e["target"]])) == key:
                        e["weight"] = min(round(e["weight"] * 1.2, 4), 1.0)
                        break
            else:
                edge_set.add(key)
                edges.append({
                    "source": src,
                    "target": tgt,
                    "weight": round(w, 4),
                    "method": "knn",
                })

    with open(GRAPH_FILE, "w") as f:
        json.dump({"edges": edges}, f, ensure_ascii=False)

    return len(edges)


# ── git ──

def git_commit(session_name: str):
    today = date.today().isoformat()
    candidates = [
        f"tasks/conversations/raw/{today}-{session_name}.jsonl",
        "memory/network/nodes.json",
        "memory/network/graph.json",
    ]
    existing = [f for f in candidates if (PROJECT_ROOT / f).exists()]
    if not existing:
        return

    subprocess.run(["git", "add"] + existing, cwd=str(PROJECT_ROOT))
    msg = (
        f"docs: {session_name} — 세션 종료 + 네트워크 갱신\n\n"
        "Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
    )
    subprocess.run(["git", "commit", "-m", msg], cwd=str(PROJECT_ROOT))


# ── 메인 ──

def main():
    parser = argparse.ArgumentParser(description="세션 종료 자동화 (v3 네트워크)")
    parser.add_argument("--name", help="세션 이름 (예: 세션20). 미지정 시 자동 결정")
    parser.add_argument("--raw-only", action="store_true", help="raw 저장만")
    parser.add_argument("--no-llm", action="store_true", help="codex 없이 raw 저장만")
    parser.add_argument("--commit", action="store_true", help="완료 후 자동 커밋")
    parser.add_argument("--dry-run", action="store_true", help="파일 미수정, stdout 출력만")
    parser.add_argument("--force", action="store_true", help="이미 종료된 세션도 강제 재실행")
    args = parser.parse_args()

    # 1. 세션 찾기
    session_jsonl = find_current_session()
    if not session_jsonl:
        print("현재 세션 JSONL을 찾을 수 없다", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    print(f"원본: {session_jsonl.name} ({session_jsonl.stat().st_size / 1024:.0f}KB)")

    # 2. 중복 체크
    already_closed_as = check_already_closed(session_jsonl)
    if already_closed_as and not args.force:
        print(f"\n이 세션은 이미 '{already_closed_as}'로 종료 처리됐다.", file=sys.stderr)
        print(f"재실행하려면 --force를 사용하라.", file=sys.stderr)
        sys.exit(1)

    if already_closed_as and args.force:
        session_name = args.name or already_closed_as.split("-")[-1]
        print(f"[force] 이미 종료된 세션 '{already_closed_as}'을 재실행한다")
    else:
        session_name = args.name or determine_session_name()

    date_session = f"{today}-{session_name}"
    print(f"세션: {date_session}")

    # 3. raw 경량 내보내기
    if not args.dry_run:
        raw_dest, count = export_raw(session_jsonl, session_name)
        size_kb = raw_dest.stat().st_size / 1024
        print(f"[완료] raw 저장 → {raw_dest.relative_to(PROJECT_ROOT)} ({count}건, {size_kb:.0f}KB)")

        mapping = load_session_map()
        mapping[get_session_uuid(session_jsonl)] = date_session
        save_session_map(mapping)
    else:
        print(f"[dry-run] raw 저장 → tasks/conversations/raw/{date_session}.jsonl")

    if args.raw_only:
        print("raw-only 모드 종료.")
        return

    # 4. 대화 추출
    print("\n대화 추출 중...")
    conversation = extract_conversation(session_jsonl, max_chars=15000)
    if not conversation.strip():
        print("대화 내용이 비어있다", file=sys.stderr)
        sys.exit(1)
    print(f"  추출: {len(conversation)}자")

    # 5. 노드 추출
    if args.no_llm:
        print("no-llm 모드. 노드 추출 건너뜀.")
        new_nodes = []
    else:
        print("\ncodex로 노드 추출 중... (최대 3분)")
        new_nodes = extract_nodes(conversation, session_name)

    print(f"  추출: {len(new_nodes)}개 노드")
    if new_nodes:
        facts = sum(1 for n in new_nodes if n.get("type") == "fact")
        intents = sum(1 for n in new_nodes if n.get("type") == "intention")
        print(f"  fact: {facts}, intention: {intents}")

    if args.dry_run:
        print("\n[dry-run] 추출된 노드:")
        for n in new_nodes[:5]:
            print(f"  [{n.get('type')}] {n.get('content', '')[:80]}")
        if len(new_nodes) > 5:
            print(f"  ... 외 {len(new_nodes) - 5}개")
        print("\n[dry-run] 파일 미수정.")
        return

    # 6. 네트워크 갱신
    if new_nodes:
        load_env()

        print("\n노드 추가 중...")
        added = add_nodes_to_network(new_nodes)
        print(f"  [완료] {added}개 노드 추가 (전체: {len(json.load(open(NODES_FILE)))}개)")

        print("임베딩 계산 중...")
        total_embs = compute_embeddings_incremental(added)
        print(f"  [완료] 임베딩 {total_embs}개")

        print("네트워크 재구축 중 (knn_k12)...")
        edge_count = rebuild_network()
        print(f"  [완료] 엣지 {edge_count}개")
    else:
        print("\n노드 없음. 네트워크 갱신 건너뜀.")

    # 7. 알림
    print("\n[수동] projects.md 업데이트 필요 여부 확인하라")

    # 8. 커밋
    if args.commit:
        git_commit(session_name)
        print("[완료] git commit")
    else:
        print("[알림] --commit 플래그로 자동 커밋 가능")


if __name__ == "__main__":
    main()
