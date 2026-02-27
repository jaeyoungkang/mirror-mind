#!/usr/bin/env python3
"""embeddings.json 전체 재생성

nodes.json의 모든 노드에 대해 OpenAI text-embedding-3-small 임베딩을 계산한다.
embeddings.json이 없거나 노드 수와 불일치할 때 실행.

사용법:
  python3 scripts/rebuild-embeddings.py          # 전체 재생성
  python3 scripts/rebuild-embeddings.py --check   # 상태만 확인
"""

import json
import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
NETWORK_DIR = PROJECT_ROOT / "memory" / "network"
NODES_FILE = NETWORK_DIR / "nodes.json"
EMBEDDINGS_FILE = NETWORK_DIR / "embeddings.json"

BATCH_SIZE = 200
MODEL = "text-embedding-3-small"


def load_env():
    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        import os
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                os.environ.setdefault(key.strip(), val.strip())


def check_status() -> tuple[int, int]:
    """노드 수와 임베딩 수 반환. 임베딩 파일 없으면 0."""
    nodes = json.load(open(NODES_FILE))
    node_count = len(nodes)

    emb_count = 0
    if EMBEDDINGS_FILE.exists():
        embs = json.load(open(EMBEDDINGS_FILE))
        emb_count = len(embs)

    return node_count, emb_count


def rebuild():
    from openai import OpenAI

    load_env()
    client = OpenAI()

    nodes = json.load(open(NODES_FILE))
    texts = [n["content"] for n in nodes]
    total = len(texts)

    print(f"노드 {total}개에 대해 임베딩 계산 시작 ({MODEL})")

    all_embs = []
    for i in range(0, total, BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        resp = client.embeddings.create(model=MODEL, input=batch)
        all_embs.extend([d.embedding for d in resp.data])
        done = min(i + BATCH_SIZE, total)
        print(f"  {done}/{total} 완료")

    with open(EMBEDDINGS_FILE, "w") as f:
        json.dump(all_embs, f)

    size_mb = EMBEDDINGS_FILE.stat().st_size / (1024 * 1024)
    print(f"[완료] {EMBEDDINGS_FILE.name} — {len(all_embs)}개 벡터, {size_mb:.1f}MB")


def main():
    parser = argparse.ArgumentParser(description="embeddings.json 전체 재생성")
    parser.add_argument("--check", action="store_true", help="상태만 확인")
    args = parser.parse_args()

    if not NODES_FILE.exists():
        print("nodes.json이 없다", file=sys.stderr)
        sys.exit(1)

    node_count, emb_count = check_status()

    if args.check:
        match = "일치" if node_count == emb_count else "불일치 — rebuild 필요"
        print(f"노드: {node_count}, 임베딩: {emb_count} ({match})")
        return

    if node_count == emb_count and EMBEDDINGS_FILE.exists():
        print(f"이미 일치 (노드: {node_count}, 임베딩: {emb_count}). 강제 재생성하려면 파일 삭제 후 재실행.")
        return

    rebuild()


if __name__ == "__main__":
    main()
