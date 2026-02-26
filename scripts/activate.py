#!/usr/bin/env python3
"""기억 활성화: 입력 맥락 → knn_k12 네트워크에서 spreading activation → 관련 기억 반환

사용법:
  python3 memory/scripts/activate.py --query "lighthouse 응답 속도 개선"
  python3 memory/scripts/activate.py --query "기억 시스템 다음 단계" --top 10
"""

import json
import argparse
import numpy as np
from pathlib import Path

NETWORK_DIR = Path(__file__).parent.parent / "memory" / "network"
NODES_PATH = NETWORK_DIR / "nodes.json"
EMBEDDINGS_PATH = NETWORK_DIR / "embeddings.json"
GRAPH_PATH = NETWORK_DIR / "graph.json"

# 확정 구조: knn_k12 단일
# 규모 대응: 노드 2배 시점마다 gate 검증 (1-hop ≤5%, avg_path ≥3.0, giant ≥70%)


def load_nodes():
    with open(NODES_PATH) as f:
        return json.load(f)


def load_embeddings():
    with open(EMBEDDINGS_PATH) as f:
        return np.array(json.load(f))


def load_graph():
    with open(GRAPH_PATH) as f:
        data = json.load(f)
    edges = data["edges"] if isinstance(data, dict) else data
    adj = {}
    for e in edges:
        s, t, w = e["source"], e["target"], e.get("weight", 1.0)
        adj.setdefault(s, []).append((t, w))
        adj.setdefault(t, []).append((s, w))
    return adj


def embed_query(query: str) -> np.ndarray | None:
    """OpenAI API로 쿼리 임베딩."""
    try:
        from openai import OpenAI
        client = OpenAI()
        resp = client.embeddings.create(model="text-embedding-3-small", input=[query])
        return np.array(resp.data[0].embedding)
    except Exception:
        return None


def find_seeds_embedding(query_emb, node_embs, top_k=3):
    """임베딩 코사인 유사도로 시드 노드 탐색."""
    norms = np.linalg.norm(node_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = node_embs / norms
    q_norm = query_emb / max(np.linalg.norm(query_emb), 1e-10)
    sims = normed @ q_norm
    topk_idx = np.argsort(sims)[-top_k:][::-1]
    return [(int(i), float(sims[i])) for i in topk_idx]


def find_seeds_text(query: str, nodes: list[dict], top_k=3):
    """API 없을 때 TF-IDF 텍스트 매칭으로 폴백."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as cos_sim
    texts = [n["content"] for n in nodes]
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    tfidf = vectorizer.fit_transform([query] + texts)
    sims = cos_sim(tfidf[0:1], tfidf[1:])[0]
    topk_idx = np.argsort(sims)[-top_k:][::-1]
    return [(int(i), float(sims[i])) for i in topk_idx]


def spread(adj, seeds, hops=2, decay=0.5):
    """시드에서 출발, hop마다 decay 적용하며 확산."""
    activation = {}
    for node_id, score in seeds:
        activation[node_id] = score
    frontier = dict(activation)
    for _ in range(hops):
        next_frontier = {}
        for node_id, score in frontier.items():
            for neighbor, weight in adj.get(node_id, []):
                new_score = score * weight * decay
                if neighbor not in activation or new_score > activation[neighbor]:
                    activation[neighbor] = new_score
                    next_frontier[neighbor] = new_score
        frontier = next_frontier
    return activation


def activate(query: str, nodes, node_embs, adj, seed_k=3, hops=2, top_n=15):
    """쿼리 → 시드 → 확산 → 상위 N개 노드 반환."""
    query_emb = embed_query(query)
    if query_emb is not None:
        seed_indices = find_seeds_embedding(query_emb, node_embs, seed_k)
    else:
        seed_indices = find_seeds_text(query, nodes, seed_k)

    seeds = [(nodes[idx]["id"], score) for idx, score in seed_indices]
    activation = spread(adj, seeds, hops=hops)
    sorted_nodes = sorted(activation.items(), key=lambda x: x[1], reverse=True)[:top_n]

    id_to_node = {n["id"]: n for n in nodes}
    results = []
    for node_id, score in sorted_nodes:
        node = id_to_node.get(node_id, {})
        results.append({
            "id": node_id,
            "score": round(score, 4),
            "content": node.get("content", ""),
            "type": node.get("type", ""),
            "session": node.get("session", ""),
        })
    return results


def extract_session_num(session_str: str) -> str:
    """'2026-02-22-세션3' → '세션3'"""
    import re
    m = re.search(r'세션(\d+)', session_str)
    return f"세션{m.group(1)}" if m else session_str


def format_for_prompt(results):
    """활성화 결과를 프롬프트 주입용 텍스트로 포맷."""
    lines = []
    for r in results:
        tag = "의도" if r["type"] == "intention" else "사실"
        session = extract_session_num(r["session"])
        lines.append(f"- [{tag}] {r['content']} ({session})")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="기억 활성화 (knn_k12 spreading activation)")
    parser.add_argument("--query", required=True, help="활성화 쿼리")
    parser.add_argument("--seeds", type=int, default=3, help="시드 노드 수 (기본: 3)")
    parser.add_argument("--hops", type=int, default=2, help="확산 홉 수 (기본: 2)")
    parser.add_argument("--top", type=int, default=15, help="반환 노드 수 (기본: 15)")
    parser.add_argument("--json", action="store_true", help="JSON 포맷 출력")
    args = parser.parse_args()

    nodes = load_nodes()
    node_embs = load_embeddings()
    adj = load_graph()

    results = activate(args.query, nodes, node_embs, adj,
                       seed_k=args.seeds, hops=args.hops, top_n=args.top)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        print(format_for_prompt(results))


if __name__ == "__main__":
    main()
