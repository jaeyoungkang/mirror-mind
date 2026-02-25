#!/usr/bin/env python3
"""V2 Phase 4: Spreading Activation + Fusion + 대화 컨텍스트 추출

활성화 소스:
- single: knn만 / cooccurrence만
- fusion: knn + cooccurrence를 3가지 전략으로 합산
  - union: 양쪽 활성화를 더함
  - intersection_boost: 양쪽 모두 활성화된 노드에 2x 가중치
  - weighted: knn 0.6 + cooc 0.4

사용법:
  /Users/jaeyoungkang/mirror-mind/memory/.venv/bin/python3 memory/simulation/v2/evaluate_v2.py
"""

import json
from pathlib import Path
from collections import defaultdict

import networkx as nx

BASE_DIR = Path(__file__).parent
NETWORKS_DIR = BASE_DIR / "networks"

# 평가 시나리오 6개
SCENARIOS = [
    {
        "id": "scenario-1",
        "input": "lighthouse 응답 속도가 느린데 어떻게 할까?",
        "description": "lighthouse 성능 개선 관련 기억 활성화",
        "seed_keywords": ["lighthouse", "응답", "속도", "느린", "orchestrator", "관측"],
    },
    {
        "id": "scenario-2",
        "input": "새 프로젝트를 시작하려고 해",
        "description": "프로젝트 시작 관련 원칙/경험 활성화",
        "seed_keywords": ["프로젝트", "시작", "원칙", "역할", "AGENTS", "체계"],
    },
    {
        "id": "scenario-3",
        "input": "온보딩 설계 어떻게 됐어?",
        "description": "온보딩/관계형성 설계 기억 활성화",
        "seed_keywords": ["온보딩", "관계", "형성", "corca", "코르카", "첫 대화"],
    },
    {
        "id": "scenario-4",
        "input": "코르카 톤이 좀 이상해",
        "description": "톤/정체성/기억주입 문제 활성화",
        "seed_keywords": ["톤", "코르카", "정체성", "기억", "주입", "인사"],
    },
    {
        "id": "scenario-5",
        "input": "메타에이전트 점검 결과 어때?",
        "description": "메타에이전트/자기감시 관련 활성화",
        "seed_keywords": ["메타에이전트", "점검", "check", "codex", "감시", "위반"],
    },
    {
        "id": "scenario-6",
        "input": "기억 시스템을 어떻게 발전시킬까?",
        "description": "기억 시스템 아키텍처 관련 활성화",
        "seed_keywords": ["기억", "시스템", "에피소드", "memories", "2레이어", "네트워크"],
    },
]


def load_network(network_dir: Path) -> nx.Graph:
    with open(network_dir / "graph.json") as f:
        data = json.load(f)
    G = nx.Graph()
    for n in data["nodes"]:
        nid = n["id"]
        G.add_node(nid, **{k: v for k, v in n.items() if k != "id"})
    for e in data["edges"]:
        G.add_edge(e["source"], e["target"], weight=e.get("weight", 1.0))
    return G


def spreading_activation(
    G: nx.Graph,
    seed_keywords: list[str],
    max_hops: int = 3,
    decay: float = 0.5,
) -> dict[str, float]:
    """Spreading activation. 활성화 점수 dict를 반환한다 (top_n 없이 전체)."""
    activation = defaultdict(float)

    # 시드 노드 활성화
    for node_id in G.nodes():
        node_data = G.nodes[node_id]
        content = node_data.get("content", "").lower()
        keywords = [k.lower() for k in node_data.get("keywords", [])]
        all_text = content + " " + " ".join(keywords)

        score = 0.0
        for kw in seed_keywords:
            if kw.lower() in all_text:
                score += 1.0
        if score > 0:
            activation[node_id] = score

    if not activation:
        return {}

    # 정규화
    max_score = max(activation.values())
    for nid in activation:
        activation[nid] /= max_score

    # BFS 전파
    for hop in range(max_hops):
        new_activation = defaultdict(float)
        for node_id, score in activation.items():
            if score <= 0.01:
                continue
            for neighbor in G.neighbors(node_id):
                edge_weight = G[node_id][neighbor].get("weight", 1.0)
                propagated = score * decay * edge_weight
                new_activation[neighbor] = max(new_activation[neighbor], propagated)
        for nid, score in new_activation.items():
            activation[nid] = max(activation[nid], score)

    return dict(activation)


def extract_top_nodes(G: nx.Graph, activation: dict[str, float], top_n: int = 15) -> list[dict]:
    """활성화 점수 상위 top_n 노드를 추출한다."""
    sorted_nodes = sorted(activation.items(), key=lambda x: x[1], reverse=True)[:top_n]
    results = []
    for node_id, score in sorted_nodes:
        node_data = dict(G.nodes[node_id])
        results.append({
            "id": node_id,
            "content": node_data.get("content", ""),
            "activation_score": round(score, 4),
            "session": node_data.get("session"),
        })
    return results


# ─── Fusion 전략 ───

def fusion_union(act_knn: dict, act_cooc: dict) -> dict:
    """양쪽 활성화를 더한다 (넓게 포착)."""
    merged = defaultdict(float)
    for nid, s in act_knn.items():
        merged[nid] += s
    for nid, s in act_cooc.items():
        merged[nid] += s
    # 정규화
    if merged:
        max_s = max(merged.values())
        if max_s > 0:
            for nid in merged:
                merged[nid] /= max_s
    return dict(merged)


def fusion_intersection_boost(act_knn: dict, act_cooc: dict) -> dict:
    """양쪽 모두 활성화된 노드에 2x 가중치 (정밀하게 포착)."""
    merged = defaultdict(float)
    all_nodes = set(act_knn.keys()) | set(act_cooc.keys())
    for nid in all_nodes:
        s_knn = act_knn.get(nid, 0)
        s_cooc = act_cooc.get(nid, 0)
        if s_knn > 0 and s_cooc > 0:
            merged[nid] = (s_knn + s_cooc) * 2.0  # intersection boost
        else:
            merged[nid] = s_knn + s_cooc
    # 정규화
    if merged:
        max_s = max(merged.values())
        if max_s > 0:
            for nid in merged:
                merged[nid] /= max_s
    return dict(merged)


def fusion_weighted(act_knn: dict, act_cooc: dict, w_knn: float = 0.6, w_cooc: float = 0.4) -> dict:
    """가중 평균 (knn 0.6 + cooc 0.4)."""
    merged = defaultdict(float)
    all_nodes = set(act_knn.keys()) | set(act_cooc.keys())
    for nid in all_nodes:
        merged[nid] = act_knn.get(nid, 0) * w_knn + act_cooc.get(nid, 0) * w_cooc
    # 정규화
    if merged:
        max_s = max(merged.values())
        if max_s > 0:
            for nid in merged:
                merged[nid] /= max_s
    return dict(merged)


FUSION_STRATEGIES = {
    "union": fusion_union,
    "intersection_boost": fusion_intersection_boost,
    "weighted": fusion_weighted,
}


def main():
    summary_path = NETWORKS_DIR / "summary.json"
    if not summary_path.exists():
        print("summary.json이 없다. build_networks_v2.py를 먼저 실행해야 한다.")
        return

    with open(summary_path) as f:
        all_stats = json.load(f)

    passed = [s for s in all_stats if s.get("gate_pass", False)]
    if not passed:
        print("Gate 통과 네트워크가 없다.")
        print("\n전체 네트워크 현황:")
        for s in all_stats:
            print(
                f"  {s['nodeset']}__{s['method']}__{s['k_label']}: "
                f"hop1={s['avg_hop1_ratio']:.3f}, "
                f"path={s['avg_path_length']}, "
                f"giant={s['giant_ratio']:.2f}"
            )
        return

    # 네트워크를 nodeset+k 기준으로 그룹핑 (fusion 조합용)
    # fusion은 gate 무관 — knn(장거리) + cooccurrence(로컬) 조합이 목적
    network_groups = defaultdict(dict)  # (nodeset, k_label) → {method: stats}
    for s in all_stats:
        key = (s["nodeset"], s["k_label"])
        network_groups[key][s["method"]] = s

    print(f"Gate 통과 네트워크 {len(passed)}개\n")

    all_contexts = {}

    # ─── 1. Single 네트워크 활성화 ───
    print("=" * 60)
    print("  SINGLE 네트워크 활성화")
    print("=" * 60)

    for stat in passed:
        network_name = f"{stat['nodeset']}__{stat['method']}__{stat['k_label']}"
        network_dir = NETWORKS_DIR / network_name
        G = load_network(network_dir)

        label = f"single/{network_name}"
        print(f"\n--- {label} ---")

        contexts = {}
        for scenario in SCENARIOS:
            activation = spreading_activation(G, scenario["seed_keywords"])
            top_nodes = extract_top_nodes(G, activation)
            contexts[scenario["id"]] = {
                "scenario_input": scenario["input"],
                "activated_nodes": top_nodes,
                "num_activated": len(top_nodes),
            }
            top3 = [f"{a['content'][:40]}({a['activation_score']:.2f})" for a in top_nodes[:3]]
            print(f"  {scenario['id']}: {len(top_nodes)} → {', '.join(top3)}")

        all_contexts[label] = contexts

    # ─── 2. Fusion 활성화 ───
    print(f"\n{'='*60}")
    print("  FUSION 활성화")
    print("=" * 60)

    for (nodeset, k_label), methods in sorted(network_groups.items()):
        if "knn" not in methods or "cooccurrence" not in methods:
            continue  # fusion에는 양쪽 모두 필요

        knn_dir = NETWORKS_DIR / f"{nodeset}__knn__{k_label}"
        cooc_dir = NETWORKS_DIR / f"{nodeset}__cooccurrence__{k_label}"
        G_knn = load_network(knn_dir)
        G_cooc = load_network(cooc_dir)

        for strategy_name, strategy_fn in FUSION_STRATEGIES.items():
            label = f"fusion-{strategy_name}/{nodeset}__{k_label}"
            print(f"\n--- {label} ---")

            contexts = {}
            for scenario in SCENARIOS:
                act_knn = spreading_activation(G_knn, scenario["seed_keywords"])
                act_cooc = spreading_activation(G_cooc, scenario["seed_keywords"])
                fused = strategy_fn(act_knn, act_cooc)
                top_nodes = extract_top_nodes(G_knn, fused)  # G_knn has all node data
                contexts[scenario["id"]] = {
                    "scenario_input": scenario["input"],
                    "activated_nodes": top_nodes,
                    "num_activated": len(top_nodes),
                }
                top3 = [f"{a['content'][:40]}({a['activation_score']:.2f})" for a in top_nodes[:3]]
                print(f"  {scenario['id']}: {len(top_nodes)} → {', '.join(top3)}")

            all_contexts[label] = contexts

    # ─── 3. 베이스라인 ───
    print(f"\n{'='*60}")
    print("  BASELINE")
    print("=" * 60)

    # 베이스라인: 빈 컨텍스트
    baseline_empty = {}
    for scenario in SCENARIOS:
        baseline_empty[scenario["id"]] = {
            "scenario_input": scenario["input"],
            "activated_nodes": [],
            "num_activated": 0,
        }
    all_contexts["baseline/empty"] = baseline_empty
    print("  baseline/empty: 준비 완료")

    # 베이스라인: 랜덤 15개 (첫 번째 통과 네트워크에서 랜덤 추출)
    if passed:
        first_stat = passed[0]
        first_dir = NETWORKS_DIR / f"{first_stat['nodeset']}__{first_stat['method']}__{first_stat['k_label']}"
        G_first = load_network(first_dir)
        import random
        random.seed(42)
        all_node_ids = list(G_first.nodes())

        baseline_random = {}
        for scenario in SCENARIOS:
            sampled = random.sample(all_node_ids, min(15, len(all_node_ids)))
            nodes = []
            for nid in sampled:
                nd = dict(G_first.nodes[nid])
                nodes.append({
                    "id": nid,
                    "content": nd.get("content", ""),
                    "activation_score": 0.5,
                    "session": nd.get("session"),
                })
            baseline_random[scenario["id"]] = {
                "scenario_input": scenario["input"],
                "activated_nodes": nodes,
                "num_activated": len(nodes),
            }
        all_contexts["baseline/random"] = baseline_random
        print("  baseline/random: 준비 완료")

    # 저장
    output_path = NETWORKS_DIR / "conversation_contexts.json"
    with open(output_path, "w") as f:
        json.dump(all_contexts, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"총 {len(all_contexts)}개 활성화 조합 생성")
    print(f"  - single: {len(passed)}개")
    fusion_count = sum(1 for k in all_contexts if k.startswith("fusion"))
    print(f"  - fusion: {fusion_count}개")
    print(f"  - baseline: 2개")
    print(f"→ {output_path}")


if __name__ == "__main__":
    main()
