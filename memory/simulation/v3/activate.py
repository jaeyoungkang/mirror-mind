#!/usr/bin/env python3
"""Spreading activation: 입력 텍스트 → 네트워크에서 관련 노드 활성화

사용법:
  python3 activate.py --query "기억 시스템 설계" --network knn__k5
  python3 activate.py --query "..." --network knn__k5 --network cooc__k5  # 혼합
"""

import json
import argparse
import numpy as np
from pathlib import Path
from openai import OpenAI
import os

BASE_DIR = Path(__file__).parent
EMBEDDINGS_CACHE = BASE_DIR / "embeddings_cache.json"
NODESET_PATH = BASE_DIR / "nodeset_v3.json"
NETWORKS_DIR = BASE_DIR / "networks"


def load_embeddings():
    with open(EMBEDDINGS_CACHE) as f:
        return np.array(json.load(f))


def load_nodes():
    with open(NODESET_PATH) as f:
        return json.load(f)


def load_graph(network_name):
    path = NETWORKS_DIR / network_name / "graph.json"
    with open(path) as f:
        data = json.load(f)
    # adjacency list
    adj = {}
    for e in data["edges"]:
        s, t, w = e["source"], e["target"], e.get("weight", 1.0)
        adj.setdefault(s, []).append((t, w))
        adj.setdefault(t, []).append((s, w))
    return adj


def embed_query(query: str) -> np.ndarray:
    """OpenAI API로 쿼리 임베딩. API 키 없으면 None 반환."""
    try:
        client = OpenAI()
        resp = client.embeddings.create(model="text-embedding-3-small", input=[query])
        return np.array(resp.data[0].embedding)
    except Exception:
        return None


def find_seed_nodes_by_text(query: str, nodes: list[dict], top_k=3):
    """API 없이 단순 텍스트 매칭으로 시드 노드 찾기."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as cos_sim

    texts = [n["content"] for n in nodes]
    all_texts = [query] + texts
    vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), min_df=1)
    tfidf = vectorizer.fit_transform(all_texts)
    sims = cos_sim(tfidf[0:1], tfidf[1:])[0]
    topk_idx = np.argsort(sims)[-top_k:][::-1]
    return [(int(i), float(sims[i])) for i in topk_idx]


def find_seed_nodes(query_emb, node_embs, top_k=3):
    """쿼리 임베딩과 가장 유사한 top_k 노드 반환."""
    norms = np.linalg.norm(node_embs, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = node_embs / norms

    q_norm = query_emb / max(np.linalg.norm(query_emb), 1e-10)
    sims = normed @ q_norm
    topk_idx = np.argsort(sims)[-top_k:][::-1]
    return [(int(i), float(sims[i])) for i in topk_idx]


def spread(adj, seeds, hops=2, decay=0.5):
    """시드에서 출발, hop마다 decay 적용하며 확산."""
    activation = {}
    for node_id, score in seeds:
        activation[node_id] = score

    frontier = dict(activation)
    for hop in range(hops):
        next_frontier = {}
        for node_id, score in frontier.items():
            for neighbor, weight in adj.get(node_id, []):
                new_score = score * weight * decay
                if neighbor not in activation or new_score > activation[neighbor]:
                    activation[neighbor] = new_score
                    next_frontier[neighbor] = new_score
        frontier = next_frontier

    return activation


def activate(query, network_names, nodes, node_embs, seed_k=3, hops=2, top_n=15):
    """쿼리 → 시드 → 확산 → 상위 N개 노드 반환. 여러 네트워크 혼합 가능."""
    query_emb = embed_query(query)
    if query_emb is not None:
        seed_indices = find_seed_nodes(query_emb, node_embs, seed_k)
    else:
        seed_indices = find_seed_nodes_by_text(query, nodes, seed_k)

    # 시드: index → node id
    seeds = [(nodes[idx]["id"], score) for idx, score in seed_indices]

    # 네트워크별 활성화 합산
    merged_activation = {}
    for net_name in network_names:
        adj = load_graph(net_name)
        activation = spread(adj, seeds, hops=hops)
        for node_id, score in activation.items():
            merged_activation[node_id] = merged_activation.get(node_id, 0) + score

    # 네트워크 수로 정규화
    n_nets = len(network_names)
    for k in merged_activation:
        merged_activation[k] /= n_nets

    # 상위 N개
    sorted_nodes = sorted(merged_activation.items(), key=lambda x: x[1], reverse=True)[:top_n]

    # 노드 ID → 내용 매핑
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
            "context_hint": node.get("context_hint", ""),
        })

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--query", required=True)
    parser.add_argument("--network", action="append", required=True, help="네트워크 이름 (여러 개 가능)")
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--hops", type=int, default=2)
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    nodes = load_nodes()
    node_embs = load_embeddings()

    results = activate(args.query, args.network, nodes, node_embs,
                       seed_k=args.seeds, hops=args.hops, top_n=args.top)

    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
