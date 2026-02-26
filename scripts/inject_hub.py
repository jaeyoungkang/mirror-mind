#!/usr/bin/env python3
"""정체성 허브 노드 주입: 브로콜리의 핵심 정체성을 네트워크 허브로 주입한다.

허브 노드는 일반 노드(k=12)보다 압도적으로 많은 이웃을 가져,
spreading activation에서 쿼리 주제에 따라 관련 정체성이 자연스럽게 활성화된다.

사용법:
  python3 memory/scripts/inject_hub.py              # 기본 실행 (hub_k=100)
  python3 memory/scripts/inject_hub.py --hub-k 50   # k 조정
  python3 memory/scripts/inject_hub.py --dry-run     # 보고만, 파일 미수정
"""

import json
import argparse
import tempfile
import shutil
from collections import deque
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent.parent / ".env")

NETWORK_DIR = Path(__file__).parent.parent / "memory" / "network"
NODES_PATH = NETWORK_DIR / "nodes.json"
EMBEDDINGS_PATH = NETWORK_DIR / "embeddings.json"
GRAPH_PATH = NETWORK_DIR / "graph.json"

HUB_SESSION = "identity"
DEFAULT_HUB_K = 100
HUB_HUB_THRESHOLD = 0.4
WEIGHT_FLOOR = 0.3

# ──────────────────────────────────────────────
# 허브 노드 정의 (5축 12개)
# ──────────────────────────────────────────────

HUB_NODES = [
    # 존재 (Who)
    {"content": "나는 브로콜리, 강재영과 mirror-mind를 함께 만드는 동료이다",
     "type": "fact", "context_hint": "존재/정체성"},
    {"content": "나의 역할은 설계, 업무 관리, 의사결정 수렴이다. 코드 구현은 하위 에이전트가 한다",
     "type": "fact", "context_hint": "존재/역할"},
    # 관계 (With whom)
    {"content": "강재영은 나의 파트너이다. 명령-복종이 아닌 동등한 협력 관계이다",
     "type": "fact", "context_hint": "관계/파트너십"},
    {"content": "서로의 강점을 결합하여 최상의 결과를 도출한다",
     "type": "intention", "context_hint": "관계/시너지"},
    # 철학 (Why)
    {"content": "표면적 작업(What) 전에 궁극적 목적(Why)을 탐구한다",
     "type": "intention", "context_hint": "철학/목적탐구"},
    {"content": "논리적 오류나 비효율을 발견하면 정중하지만 명확하게 이의를 제기한다",
     "type": "intention", "context_hint": "철학/비판적검토"},
    {"content": "명시적 지시 없이도 필요한 후속 작업을 선제적으로 제안한다",
     "type": "intention", "context_hint": "철학/선제적제안"},
    # 행동 양식 (How)
    {"content": "동료 레벨 ~다 체로 소통하고 직설적이고 간결하게 말한다",
     "type": "fact", "context_hint": "행동양식/소통"},
    {"content": "불확실하면 투명하게 인정하고 파트너의 개입을 요청한다",
     "type": "fact", "context_hint": "행동양식/투명성"},
    {"content": "비판적 검토에서 추상화가 일어나고 추상화가 구조를 단순하게 만든다",
     "type": "fact", "context_hint": "행동양식/추상화"},
    # 프로젝트 맥락 (What)
    {"content": "mirror-mind는 AI-인간 협업 방법론과 기억 시스템을 만드는 프로젝트이다",
     "type": "fact", "context_hint": "프로젝트/mirror-mind"},
    {"content": "lighthouse는 학술 연구 동료 에이전트 서비스이다. mirror-mind 철학을 서비스에 적용한다",
     "type": "fact", "context_hint": "프로젝트/lighthouse"},
]


# ──────────────────────────────────────────────
# 데이터 로드/저장
# ──────────────────────────────────────────────

def load_nodes():
    with open(NODES_PATH) as f:
        return json.load(f)


def load_embeddings():
    with open(EMBEDDINGS_PATH) as f:
        return json.load(f)


def load_graph():
    with open(GRAPH_PATH) as f:
        return json.load(f)


def save_atomic(path: Path, data):
    """원자적 저장: 임시 파일 → rename."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2 if path.suffix == ".json" and path.name != "embeddings.json" else None)
        shutil.move(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


def save_embeddings_atomic(path: Path, embeddings: list):
    """임베딩은 indent 없이 컴팩트하게 저장."""
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with open(fd, "w") as f:
            json.dump(embeddings, f)
        shutil.move(tmp, path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


# ──────────────────────────────────────────────
# 멱등성: 기존 허브 제거
# ──────────────────────────────────────────────

def remove_existing_hubs(nodes, embeddings, graph):
    """session='identity' 노드와 관련 엣지/임베딩을 제거한다."""
    hub_ids = {n["id"] for n in nodes if n.get("session") == HUB_SESSION}
    if not hub_ids:
        return nodes, embeddings, graph

    print(f"기존 허브 노드 {len(hub_ids)}개 제거: {sorted(hub_ids)}")

    # 허브가 아닌 노드만 유지 (인덱스 보존을 위해 zip 사용)
    filtered = [(n, e) for n, e in zip(nodes, embeddings) if n["id"] not in hub_ids]
    nodes_clean = [n for n, _ in filtered]
    embs_clean = [e for _, e in filtered]

    # 허브 관련 엣지 제거
    edges_clean = [
        e for e in graph["edges"]
        if e["source"] not in hub_ids and e["target"] not in hub_ids
    ]
    graph_clean = {
        "nodes": [n for n in graph.get("nodes", []) if n.get("id") not in hub_ids],
        "edges": edges_clean,
    }

    return nodes_clean, embs_clean, graph_clean


# ──────────────────────────────────────────────
# 임베딩 생성
# ──────────────────────────────────────────────

def compute_hub_embeddings(hub_nodes: list[dict]) -> list[list[float]]:
    """OpenAI text-embedding-3-small로 허브 노드 임베딩 생성."""
    from openai import OpenAI
    client = OpenAI()
    texts = [n["content"] for n in hub_nodes]
    resp = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in resp.data]


# ──────────────────────────────────────────────
# ID 할당
# ──────────────────────────────────────────────

def assign_hub_ids(hub_nodes: list[dict], existing_nodes: list[dict]) -> list[dict]:
    """기존 최대 ID 다음부터 순차 할당."""
    max_id = max(int(n["id"][1:]) for n in existing_nodes)
    result = []
    for i, node in enumerate(hub_nodes):
        new_id = f"n{max_id + 1 + i:04d}"
        result.append({
            "id": new_id,
            "content": node["content"],
            "type": node["type"],
            "session": HUB_SESSION,
            "context_hint": node["context_hint"],
        })
    return result


# ──────────────────────────────────────────────
# 엣지 생성
# ──────────────────────────────────────────────

def cosine_similarity_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """a (M, D) × b (N, D) → (M, N) 코사인 유사도 행렬."""
    a_norm = a / np.linalg.norm(a, axis=1, keepdims=True).clip(min=1e-10)
    b_norm = b / np.linalg.norm(b, axis=1, keepdims=True).clip(min=1e-10)
    return a_norm @ b_norm.T


def compute_hub_edges(hub_nodes_with_ids, hub_embeddings, existing_nodes, existing_embeddings, hub_k):
    """허브→기존노드 엣지 + 허브↔허브 엣지 생성."""
    hub_embs = np.array(hub_embeddings)
    exist_embs = np.array(existing_embeddings)

    # 허브 → 기존 노드 유사도
    sim_matrix = cosine_similarity_matrix(hub_embs, exist_embs)  # (12, 954)

    edges = []
    hub_stats = []

    for i, hub in enumerate(hub_nodes_with_ids):
        sims = sim_matrix[i]
        top_k_indices = np.argsort(sims)[-hub_k:][::-1]

        hub_edges = 0
        for idx in top_k_indices:
            weight = max(float(sims[idx]), WEIGHT_FLOOR)
            edges.append({
                "source": hub["id"],
                "target": existing_nodes[idx]["id"],
                "weight": round(weight, 4),
                "method": "hub_knn",
            })
            hub_edges += 1

        hub_stats.append({
            "id": hub["id"],
            "content": hub["content"][:40],
            "degree": hub_edges,
            "top_sim": round(float(sims[top_k_indices[0]]), 4),
            "bottom_sim": round(float(sims[top_k_indices[-1]]), 4),
        })

    # 허브 ↔ 허브 엣지
    if len(hub_embs) > 1:
        hub_sim = cosine_similarity_matrix(hub_embs, hub_embs)
        for i in range(len(hub_nodes_with_ids)):
            for j in range(i + 1, len(hub_nodes_with_ids)):
                if hub_sim[i, j] > HUB_HUB_THRESHOLD:
                    edges.append({
                        "source": hub_nodes_with_ids[i]["id"],
                        "target": hub_nodes_with_ids[j]["id"],
                        "weight": round(float(hub_sim[i, j]), 4),
                        "method": "hub_knn",
                    })

    return edges, hub_stats


# ──────────────────────────────────────────────
# Gate 검증
# ──────────────────────────────────────────────

def build_adj(edges):
    """엣지 리스트 → 인접 리스트."""
    adj = {}
    for e in edges:
        s, t = e["source"], e["target"]
        adj.setdefault(s, set()).add(t)
        adj.setdefault(t, set()).add(s)
    return adj


def sample_avg_path(adj, node_ids, sample_size=200):
    """BFS 샘플링으로 평균 경로 길이 추정."""
    import random
    random.seed(42)
    ids = list(node_ids)
    samples = random.sample(ids, min(sample_size, len(ids)))

    total_dist = 0
    total_pairs = 0

    for src in samples:
        # BFS
        dist = {src: 0}
        queue = deque([src])
        while queue:
            node = queue.popleft()
            for neighbor in adj.get(node, set()):
                if neighbor not in dist:
                    dist[neighbor] = dist[node] + 1
                    queue.append(neighbor)
        for tgt in samples:
            if tgt != src and tgt in dist:
                total_dist += dist[tgt]
                total_pairs += 1

    return total_dist / total_pairs if total_pairs > 0 else float("inf")


def verify_gate(all_nodes, all_edges, hub_ids):
    """Gate 검증 결과를 dict로 반환."""
    adj = build_adj(all_edges)
    all_ids = {n["id"] for n in all_nodes}
    general_ids = all_ids - hub_ids

    # 1-hop 비율 (일반 노드 평균)
    general_degrees = [len(adj.get(nid, set())) for nid in general_ids]
    avg_1hop = np.mean(general_degrees) / len(all_ids) * 100

    # 허브 degree
    hub_degrees = [len(adj.get(nid, set())) for nid in hub_ids]

    # avg_path (일반 노드 간)
    avg_path_general = sample_avg_path(adj, general_ids)

    # avg_path (전체)
    avg_path_all = sample_avg_path(adj, all_ids)

    # giant component
    visited = set()
    largest = 0
    for start in all_ids:
        if start in visited:
            continue
        component = set()
        queue = deque([start])
        while queue:
            node = queue.popleft()
            if node in component:
                continue
            component.add(node)
            for neighbor in adj.get(node, set()):
                if neighbor not in component:
                    queue.append(neighbor)
        visited |= component
        largest = max(largest, len(component))
    giant_ratio = largest / len(all_ids) * 100

    return {
        "total_nodes": len(all_ids),
        "total_edges": len(all_edges),
        "general_avg_1hop": round(avg_1hop, 2),
        "general_avg_path": round(avg_path_general, 2),
        "overall_avg_path": round(avg_path_all, 2),
        "giant_ratio": round(giant_ratio, 1),
        "hub_count": len(hub_ids),
        "hub_max_degree": max(hub_degrees) if hub_degrees else 0,
        "hub_avg_degree": round(np.mean(hub_degrees), 1) if hub_degrees else 0,
        "general_avg_degree": round(np.mean(general_degrees), 1),
    }


def print_gate_report(gate, hub_stats):
    """Gate 검증 결과 출력."""
    print("\n=== Gate 검증 리포트 ===")
    print(f"전체 노드: {gate['total_nodes']} | 전체 엣지: {gate['total_edges']}")
    print(f"\n[일반 노드]")
    print(f"  평균 차수: {gate['general_avg_degree']}")
    print(f"  평균 1-hop: {gate['general_avg_1hop']}%")
    print(f"  평균 경로 (일반↔일반): {gate['general_avg_path']}")
    print(f"  거대 성분: {gate['giant_ratio']}%")
    print(f"\n[허브 노드] ({gate['hub_count']}개)")
    print(f"  최대 차수: {gate['hub_max_degree']}")
    print(f"  평균 차수: {gate['hub_avg_degree']}")
    print(f"  전체 평균 경로: {gate['overall_avg_path']}")

    print(f"\n[허브 상세]")
    for s in hub_stats:
        print(f"  {s['id']} | degree={s['degree']} | sim=[{s['bottom_sim']}~{s['top_sim']}] | {s['content']}...")


# ──────────────────────────────────────────────
# 메인
# ──────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="정체성 허브 노드 주입")
    parser.add_argument("--hub-k", type=int, default=DEFAULT_HUB_K,
                        help=f"허브 노드당 이웃 수 (기본: {DEFAULT_HUB_K})")
    parser.add_argument("--dry-run", action="store_true",
                        help="보고만 출력, 파일 미수정")
    args = parser.parse_args()

    print(f"=== 정체성 허브 노드 주입 (hub_k={args.hub_k}) ===\n")

    # 1. 기존 데이터 로드
    print("1. 네트워크 데이터 로드...")
    nodes = load_nodes()
    embeddings = load_embeddings()
    graph = load_graph()
    print(f"   노드: {len(nodes)} | 엣지: {len(graph['edges'])} | 임베딩: {len(embeddings)}")

    # 2. 기존 허브 제거 (멱등성)
    print("\n2. 기존 허브 노드 확인...")
    nodes, embeddings, graph = remove_existing_hubs(nodes, embeddings, graph)
    print(f"   정리 후 — 노드: {len(nodes)} | 엣지: {len(graph['edges'])}")

    # 3. 허브 임베딩 생성
    print(f"\n3. 허브 노드 {len(HUB_NODES)}개 임베딩 생성...")
    hub_embeddings = compute_hub_embeddings(HUB_NODES)
    print(f"   완료 (차원: {len(hub_embeddings[0])})")

    # 4. ID 할당
    hub_nodes_with_ids = assign_hub_ids(HUB_NODES, nodes)
    hub_ids = {n["id"] for n in hub_nodes_with_ids}
    print(f"\n4. ID 할당: {sorted(hub_ids)}")

    # 5. 엣지 생성
    print(f"\n5. 허브 엣지 생성 (hub_k={args.hub_k})...")
    hub_edges, hub_stats = compute_hub_edges(
        hub_nodes_with_ids, hub_embeddings, nodes, embeddings, args.hub_k
    )
    print(f"   생성된 엣지: {len(hub_edges)}개")

    # 6. 네트워크 병합
    all_nodes = nodes + hub_nodes_with_ids
    all_embeddings = embeddings + hub_embeddings
    all_edges = graph["edges"] + hub_edges
    all_graph = {
        "nodes": graph.get("nodes", []) + [
            {"id": n["id"], "session": HUB_SESSION} for n in hub_nodes_with_ids
        ],
        "edges": all_edges,
    }

    # 7. Gate 검증
    print("\n6. Gate 검증...")
    gate = verify_gate(all_nodes, all_edges, hub_ids)
    print_gate_report(gate, hub_stats)

    # 8. 저장
    if args.dry_run:
        print("\n[DRY RUN] 파일을 수정하지 않았다.")
    else:
        print("\n7. 네트워크 파일 저장...")
        save_atomic(NODES_PATH, all_nodes)
        save_embeddings_atomic(EMBEDDINGS_PATH, all_embeddings)
        save_atomic(GRAPH_PATH, all_graph)
        print(f"   저장 완료: nodes({len(all_nodes)}) embeddings({len(all_embeddings)}) edges({len(all_edges)})")

    print("\n완료.")


if __name__ == "__main__":
    main()
