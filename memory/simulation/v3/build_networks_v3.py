#!/usr/bin/env python3
"""V3: OpenAI 임베딩 기반 네트워크 구축

노드: 954개 fact/intention (raw JSONL에서 직접 추출)
링크: knn(임베딩) + cooccurrence(세션 내 인접) → fusion
파라미터: k=5,8,12,16 (v2 대비 노드 4.3배이므로 k 범위 확장)

사용법:
  /Users/jaeyoungkang/mirror-mind/memory/.venv/bin/python3 memory/simulation/v3/build_networks_v3.py
"""

import json
import os
import time
from pathlib import Path
from collections import defaultdict

import networkx as nx
import numpy as np
from openai import OpenAI

BASE_DIR = Path(__file__).parent
NODESET_PATH = BASE_DIR / "nodeset_v3.json"
NETWORKS_DIR = BASE_DIR / "networks"
EMBEDDINGS_CACHE = BASE_DIR / "embeddings_cache.json"
NETWORKS_DIR.mkdir(exist_ok=True)

# .env 로드
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

K_VALUES = {"k5": 5, "k8": 8, "k12": 12, "k16": 16}


def load_nodes() -> list[dict]:
    with open(NODESET_PATH) as f:
        return json.load(f)


def get_embeddings(nodes: list[dict]) -> np.ndarray:
    """OpenAI text-embedding-3-small로 임베딩 생성. 캐시 사용."""
    if EMBEDDINGS_CACHE.exists():
        print("  임베딩 캐시 로드...")
        with open(EMBEDDINGS_CACHE) as f:
            cached = json.load(f)
        if len(cached) == len(nodes):
            return np.array(cached)
        print(f"  캐시 크기 불일치 ({len(cached)} vs {len(nodes)}), 재생성...")

    client = OpenAI()
    texts = [n["content"] for n in nodes]

    print(f"  {len(texts)}개 텍스트 임베딩 생성 중...")
    all_embeddings = []

    # 배치 처리 (API 제한 고려, 100개씩)
    batch_size = 100
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=batch,
        )
        batch_embs = [item.embedding for item in response.data]
        all_embeddings.extend(batch_embs)
        print(f"    {min(i + batch_size, len(texts))}/{len(texts)}")
        if i + batch_size < len(texts):
            time.sleep(0.1)  # rate limit 방지

    # 캐시 저장
    with open(EMBEDDINGS_CACHE, "w") as f:
        json.dump(all_embeddings, f)
    print(f"  임베딩 캐시 저장: {EMBEDDINGS_CACHE}")

    return np.array(all_embeddings)


def cosine_sim_matrix(embeddings: np.ndarray) -> np.ndarray:
    """정규화된 임베딩의 코사인 유사도 행렬."""
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = embeddings / norms
    return normed @ normed.T


# ─── knn 링크 ───

def build_knn_edges(nodes: list[dict], k: int, sim_matrix: np.ndarray) -> list[tuple]:
    n = len(nodes)
    if n < 2:
        return []

    directed = defaultdict(dict)
    for i in range(n):
        sims = sim_matrix[i].copy()
        sims[i] = -1
        topk = np.argsort(sims)[-k:]
        for j in topk:
            if sims[j] > 0:
                directed[i][j] = float(sims[j])

    edges = {}
    for i in directed:
        for j, w in directed[i].items():
            pair = (min(i, j), max(i, j))
            if pair in edges:
                edges[pair] = max(edges[pair], w) * 1.2
            else:
                edges[pair] = w

    return [
        (nodes[i]["id"], nodes[j]["id"], {"weight": round(min(w, 1.0), 4), "method": "knn"})
        for (i, j), w in edges.items()
    ]


# ─── cooccurrence 링크 ───

def build_cooccurrence_edges(nodes: list[dict], k: int) -> list[tuple]:
    session_groups = defaultdict(list)
    for idx, n in enumerate(nodes):
        session = n.get("session")
        if session:
            session_groups[session].append(idx)

    candidate_pairs = defaultdict(float)
    for session, indices in session_groups.items():
        indices_sorted = sorted(indices, key=lambda x: nodes[x]["id"])
        for a in range(len(indices_sorted)):
            for b in range(a + 1, len(indices_sorted)):
                i, j = indices_sorted[a], indices_sorted[b]
                dist = b - a
                if dist <= 3:
                    weight = 1.0 / (1.0 + dist * 0.5)
                    pair = (min(i, j), max(i, j))
                    candidate_pairs[pair] = max(candidate_pairs.get(pair, 0), weight)

    node_edges = defaultdict(list)
    for (i, j), w in candidate_pairs.items():
        node_edges[i].append((j, w))
        node_edges[j].append((i, w))

    selected = set()
    for node_idx, neighbors in node_edges.items():
        neighbors.sort(key=lambda x: x[1], reverse=True)
        for other, w in neighbors[:k]:
            pair = (min(node_idx, other), max(node_idx, other))
            selected.add((pair, w))

    return [
        (nodes[i]["id"], nodes[j]["id"], {"weight": round(w, 4), "method": "cooccurrence"})
        for (i, j), w in selected
    ]


# ─── fusion ───

def build_fusion_network(nodes, knn_edges, cooc_edges, alpha=0.6):
    """knn과 cooccurrence를 가중 합산. alpha=knn 비중."""
    edge_map = {}

    for src, tgt, data in knn_edges:
        pair = (min(src, tgt), max(src, tgt))
        edge_map[pair] = {"knn": data["weight"], "cooc": 0.0}

    for src, tgt, data in cooc_edges:
        pair = (min(src, tgt), max(src, tgt))
        if pair in edge_map:
            edge_map[pair]["cooc"] = data["weight"]
        else:
            edge_map[pair] = {"knn": 0.0, "cooc": data["weight"]}

    edges = []
    for (src, tgt), weights in edge_map.items():
        fused = alpha * weights["knn"] + (1 - alpha) * weights["cooc"]
        if fused > 0:
            edges.append((src, tgt, {"weight": round(fused, 4), "method": "fusion"}))

    return edges


# ─── 네트워크 통계 ───

def compute_stats(G, label_parts):
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    degrees = dict(G.degree())
    avg_degree = round(sum(degrees.values()) / max(num_nodes, 1), 2)
    num_components = nx.number_connected_components(G)

    if num_components > 0:
        giant = max(nx.connected_components(G), key=len)
        giant_ratio = round(len(giant) / num_nodes, 4)
    else:
        giant_ratio = 0

    # 1-hop 도달률
    sample_nodes = list(G.nodes())[:min(30, num_nodes)]
    hop1_ratios = [len(set(G.neighbors(s))) / max(num_nodes - 1, 1) for s in sample_nodes]
    avg_hop1 = round(sum(hop1_ratios) / max(len(hop1_ratios), 1), 4)

    # 평균 최단 경로
    avg_path = -1
    if giant_ratio > 0.5:
        giant_sub = G.subgraph(max(nx.connected_components(G), key=len))
        try:
            avg_path = round(nx.average_shortest_path_length(giant_sub), 2)
        except nx.NetworkXError:
            pass

    clustering = round(nx.average_clustering(G), 4)

    gate_pass = avg_hop1 <= 0.05 and avg_path >= 3.0 and giant_ratio >= 0.70

    # 허브
    degree_sorted = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:5]
    hubs = [
        {"id": n, "degree": d, "content": G.nodes[n].get("content", "")[:60]}
        for n, d in degree_sorted
    ]

    return {
        **label_parts,
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "avg_degree": avg_degree,
        "num_components": num_components,
        "giant_ratio": giant_ratio,
        "avg_hop1_ratio": avg_hop1,
        "avg_path_length": avg_path,
        "clustering_coeff": clustering,
        "density": round(nx.density(G), 4),
        "gate_pass": gate_pass,
        "hub_nodes": hubs,
    }


def make_graph(nodes, edges):
    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
    G.add_edges_from(edges)
    return G


def save_network(name, G, stats):
    net_dir = NETWORKS_DIR / name
    net_dir.mkdir(exist_ok=True)

    net_data = {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes()],
        "edges": [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)],
    }
    with open(net_dir / "graph.json", "w") as f:
        json.dump(net_data, f, ensure_ascii=False, indent=2)
    with open(net_dir / "stats.json", "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)


def main():
    nodes = load_nodes()
    print(f"노드 {len(nodes)}개 로드")

    # 1. 임베딩
    embeddings = get_embeddings(nodes)
    sim_matrix = cosine_sim_matrix(embeddings)
    print(f"유사도 행렬: {sim_matrix.shape}")

    all_stats = []

    for k_label, k in K_VALUES.items():
        print(f"\n--- k={k} ({k_label}) ---")

        # 2. knn
        knn_edges = build_knn_edges(nodes, k, sim_matrix)
        G_knn = make_graph(nodes, knn_edges)
        stats_knn = compute_stats(G_knn, {"method": "knn", "k_label": k_label, "k": k})
        save_network(f"knn__{k_label}", G_knn, stats_knn)
        gate = "PASS" if stats_knn["gate_pass"] else "FAIL"
        print(f"  knn:  edges={stats_knn['num_edges']:>5}, hop1={stats_knn['avg_hop1_ratio']:.3f}, path={stats_knn['avg_path_length']:>5}, giant={stats_knn['giant_ratio']:.2f} [{gate}]")
        all_stats.append(stats_knn)

        # 3. cooccurrence
        cooc_edges = build_cooccurrence_edges(nodes, k)
        G_cooc = make_graph(nodes, cooc_edges)
        stats_cooc = compute_stats(G_cooc, {"method": "cooccurrence", "k_label": k_label, "k": k})
        save_network(f"cooc__{k_label}", G_cooc, stats_cooc)
        gate = "PASS" if stats_cooc["gate_pass"] else "FAIL"
        print(f"  cooc: edges={stats_cooc['num_edges']:>5}, hop1={stats_cooc['avg_hop1_ratio']:.3f}, path={stats_cooc['avg_path_length']:>5}, giant={stats_cooc['giant_ratio']:.2f} [{gate}]")
        all_stats.append(stats_cooc)

        # 4. fusion (alpha=0.6 knn 비중)
        fusion_edges = build_fusion_network(nodes, knn_edges, cooc_edges, alpha=0.6)
        G_fusion = make_graph(nodes, fusion_edges)
        stats_fusion = compute_stats(G_fusion, {"method": "fusion", "k_label": k_label, "k": k, "alpha": 0.6})
        save_network(f"fusion__{k_label}", G_fusion, stats_fusion)
        gate = "PASS" if stats_fusion["gate_pass"] else "FAIL"
        print(f"  fuse: edges={stats_fusion['num_edges']:>5}, hop1={stats_fusion['avg_hop1_ratio']:.3f}, path={stats_fusion['avg_path_length']:>5}, giant={stats_fusion['giant_ratio']:.2f} [{gate}]")
        all_stats.append(stats_fusion)

    # 요약
    with open(NETWORKS_DIR / "summary.json", "w") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    passed = [s for s in all_stats if s["gate_pass"]]
    print(f"\n{'='*60}")
    print(f"총 {len(all_stats)}개 네트워크 중 {len(passed)}개 gate 통과")
    for s in passed:
        print(f"  {s['method']}/{s['k_label']}: hop1={s['avg_hop1_ratio']:.3f}, path={s['avg_path_length']}, giant={s['giant_ratio']:.2f}")


if __name__ == "__main__":
    main()
