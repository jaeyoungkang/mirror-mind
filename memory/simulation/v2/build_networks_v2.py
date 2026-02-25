#!/usr/bin/env python3
"""V2: 노드세트 × 링크방법(knn, cooccurrence) × 밀도(k) → 네트워크 생성

교훈 반영:
- threshold 대신 k-NN으로 밀도 직접 제어
- temporal cross-session 제거, 인접 에피소드만
- hybrid는 빌드 단계가 아니라 평가 단계에서 fusion으로 처리

사용법:
  /Users/jaeyoungkang/mirror-mind/memory/.venv/bin/python3 memory/simulation/v2/build_networks_v2.py
"""

import json
import math
from pathlib import Path
from collections import defaultdict
from itertools import combinations

import networkx as nx
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np

BASE_DIR = Path(__file__).parent
NODESETS_DIR = BASE_DIR / "nodesets"
NETWORKS_DIR = BASE_DIR / "networks"
NETWORKS_DIR.mkdir(exist_ok=True)

# 밀도 제어: k값 (각 노드에서 top-k 이웃 연결)
K_VALUES = {"k3": 3, "k5": 5, "k8": 8}


def load_nodeset(name: str) -> list[dict]:
    path = NODESETS_DIR / f"{name}.json"
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def compute_similarity_matrix(nodes: list[dict]) -> np.ndarray:
    """TF-IDF cosine similarity matrix를 계산한다."""
    texts = []
    for n in nodes:
        parts = []
        if n.get("content"):
            parts.append(n["content"])
        if n.get("keywords"):
            parts.append(" ".join(n["keywords"]))
        texts.append(" ".join(parts))

    if all(not t.strip() for t in texts):
        return np.zeros((len(nodes), len(nodes)))

    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        min_df=1,
        max_df=0.95,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(texts)
    except ValueError:
        return np.zeros((len(nodes), len(nodes)))

    return cosine_similarity(tfidf_matrix)


# ─── 링크 방법 1: k-NN Content ───

def build_knn_edges(nodes: list[dict], k: int, sim_matrix: np.ndarray) -> list[tuple]:
    """각 노드에서 가장 유사한 top-k 이웃으로 연결.
    양방향이면 weight boost (1.2x)."""
    n = len(nodes)
    if n < 2:
        return []

    # 각 노드의 top-k 이웃 찾기
    directed = defaultdict(dict)  # directed[i][j] = sim
    for i in range(n):
        sims = sim_matrix[i].copy()
        sims[i] = -1  # 자기 자신 제외
        # top-k indices
        topk = np.argsort(sims)[-k:]
        for j in topk:
            if sims[j] > 0:
                directed[i][j] = float(sims[j])

    # 양방향 병합: i→j와 j→i 둘 다 있으면 boost
    edges = {}
    for i in directed:
        for j, w in directed[i].items():
            pair = (min(i, j), max(i, j))
            if pair in edges:
                # 양방향 → boost
                edges[pair] = max(edges[pair], w) * 1.2
            else:
                edges[pair] = w

    result = []
    for (i, j), w in edges.items():
        result.append((
            nodes[i]["id"], nodes[j]["id"],
            {"weight": round(min(w, 1.0), 4), "method": "knn"}
        ))
    return result


# ─── 링크 방법 2: Co-occurrence ───

def build_cooccurrence_edges(nodes: list[dict], k: int) -> list[tuple]:
    """같은 에피소드 또는 인접 에피소드(episode_index ±1)에서 파생된 노드끼리 연결.
    cross-session 연결 없음.
    k 파라미터: 한 노드당 최대 co-occurrence 연결 수."""

    # 세션 + 에피소드 인덱스로 노드 그룹핑
    # 노드에 session 필드가 있으면 사용, 없으면 (entity 등) 스킵
    session_groups = defaultdict(list)  # session → [(node_idx, episode_index_approx)]
    for idx, n in enumerate(nodes):
        session = n.get("session")
        if not session:
            continue
        session_groups[session].append(idx)

    # 같은 세션 내 노드들을 순서대로 연결
    candidate_pairs = defaultdict(float)  # (i,j) → weight

    for session, indices in session_groups.items():
        # 세션 내 노드들 — 등장 순서(ID순)로 인접 노드끼리 연결
        indices_sorted = sorted(indices, key=lambda x: nodes[x]["id"])

        for a in range(len(indices_sorted)):
            for b in range(a + 1, len(indices_sorted)):
                i, j = indices_sorted[a], indices_sorted[b]
                # 거리가 가까울수록 weight 높음
                dist = b - a
                if dist <= 3:  # 같은 세션 내 가까운 노드만
                    weight = 1.0 / (1.0 + dist * 0.5)
                    pair = (min(i, j), max(i, j))
                    candidate_pairs[pair] = max(candidate_pairs.get(pair, 0), weight)

    # 각 노드별 top-k co-occurrence 연결만 유지
    node_edges = defaultdict(list)  # node_idx → [(other_idx, weight)]
    for (i, j), w in candidate_pairs.items():
        node_edges[i].append((j, w))
        node_edges[j].append((i, w))

    # 각 노드에서 top-k만 선택
    selected = set()
    for node_idx, neighbors in node_edges.items():
        neighbors.sort(key=lambda x: x[1], reverse=True)
        for other, w in neighbors[:k]:
            pair = (min(node_idx, other), max(node_idx, other))
            selected.add((pair, w))

    result = []
    for (i, j), w in selected:
        result.append((
            nodes[i]["id"], nodes[j]["id"],
            {"weight": round(w, 4), "method": "cooccurrence"}
        ))
    return result


# ─── 네트워크 구축 + 저장 ───

def build_and_save(nodeset_name: str, nodes: list[dict], method: str, k_label: str, k: int):
    """네트워크를 생성하고 저장한다."""
    sim_matrix = None
    if method == "knn":
        sim_matrix = compute_similarity_matrix(nodes)

    if method == "knn":
        edges = build_knn_edges(nodes, k, sim_matrix)
    elif method == "cooccurrence":
        edges = build_cooccurrence_edges(nodes, k)
    else:
        raise ValueError(f"Unknown method: {method}")

    G = nx.Graph()
    for n in nodes:
        G.add_node(n["id"], **{key: val for key, val in n.items() if key != "id"})
    G.add_edges_from(edges)

    # 통계
    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    degrees = dict(G.degree())
    avg_degree = round(sum(degrees.values()) / max(num_nodes, 1), 2)
    num_components = nx.number_connected_components(G)

    # Giant component
    if num_components > 0:
        giant = max(nx.connected_components(G), key=len)
        giant_ratio = round(len(giant) / num_nodes, 4)
    else:
        giant_ratio = 0

    # 1-hop 도달률: 랜덤 10개 시드의 평균
    hop1_ratios = []
    sample_nodes = list(G.nodes())[:min(20, num_nodes)]
    for seed in sample_nodes:
        neighbors = set(G.neighbors(seed))
        hop1_ratios.append(len(neighbors) / max(num_nodes - 1, 1))
    avg_hop1 = round(sum(hop1_ratios) / max(len(hop1_ratios), 1), 4)

    # 평균 최단 경로 (giant component에서)
    if giant_ratio > 0.5:
        giant_subgraph = G.subgraph(giant)
        try:
            avg_path = round(nx.average_shortest_path_length(giant_subgraph), 2)
        except nx.NetworkXError:
            avg_path = -1
    else:
        avg_path = -1

    # 클러스터링 계수
    clustering = round(nx.average_clustering(G), 4)

    stats = {
        "nodeset": nodeset_name,
        "method": method,
        "k_label": k_label,
        "k": k,
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "avg_degree": avg_degree,
        "num_components": num_components,
        "giant_ratio": giant_ratio,
        "avg_hop1_ratio": avg_hop1,
        "avg_path_length": avg_path,
        "clustering_coeff": clustering,
        "density": round(nx.density(G), 4),
    }

    # 허브 노드 (degree 상위 5개)
    degree_sorted = sorted(G.degree(), key=lambda x: x[1], reverse=True)[:5]
    stats["hub_nodes"] = [
        {"id": n, "degree": d, "content": G.nodes[n].get("content", "")[:60]}
        for n, d in degree_sorted
    ]

    # Gate 검증
    gate_pass = (
        avg_hop1 <= 0.05
        and avg_path >= 3.0
        and giant_ratio >= 0.70
    )
    stats["gate_pass"] = gate_pass

    # 저장
    network_name = f"{nodeset_name}__{method}__{k_label}"
    network_dir = NETWORKS_DIR / network_name
    network_dir.mkdir(exist_ok=True)

    net_data = {
        "nodes": [{"id": n, **G.nodes[n]} for n in G.nodes()],
        "edges": [{"source": u, "target": v, **d} for u, v, d in G.edges(data=True)],
    }
    with open(network_dir / "graph.json", "w") as f:
        json.dump(net_data, f, ensure_ascii=False, indent=2)

    with open(network_dir / "stats.json", "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    return stats


def main():
    nodeset_files = list(NODESETS_DIR.glob("*.json"))
    if not nodeset_files:
        print("노드세트 파일이 없다.")
        return

    methods = ["knn", "cooccurrence"]
    all_stats = []

    for nf in sorted(nodeset_files):
        nodeset_name = nf.stem
        nodes = load_nodeset(nodeset_name)
        if not nodes:
            print(f"[SKIP] {nodeset_name}: 노드 없음")
            continue

        print(f"\n{'='*60}")
        print(f"  {nodeset_name} ({len(nodes)} nodes)")
        print(f"{'='*60}")

        for method in methods:
            for k_label, k in K_VALUES.items():
                stats = build_and_save(nodeset_name, nodes, method, k_label, k)
                gate = "✓" if stats["gate_pass"] else "✗"
                print(
                    f"  {method}/{k_label}: "
                    f"edges={stats['num_edges']:>4}, "
                    f"avg_deg={stats['avg_degree']:>5}, "
                    f"hop1={stats['avg_hop1_ratio']:.3f}, "
                    f"path={stats['avg_path_length']:>5}, "
                    f"giant={stats['giant_ratio']:.2f}, "
                    f"clust={stats['clustering_coeff']:.3f}  "
                    f"[{gate}]"
                )
                all_stats.append(stats)

    # 전체 요약
    with open(NETWORKS_DIR / "summary.json", "w") as f:
        json.dump(all_stats, f, ensure_ascii=False, indent=2)

    passed = [s for s in all_stats if s["gate_pass"]]
    print(f"\n{'='*60}")
    print(f"총 {len(all_stats)}개 네트워크 중 {len(passed)}개 gate 통과")
    print(f"→ {NETWORKS_DIR}/summary.json")


if __name__ == "__main__":
    main()
