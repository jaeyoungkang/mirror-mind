# 정체성 허브 노드 구현 프롬프트

> 배경: 기억 시스템 v3 네트워크에서 코르카의 정체성 노드가 일반 노드와 동일한 k=12로 연결되어 있다.
> 대화가 쌓이면 경험 노드에 묻힌다. 정체성 노드를 허브(이웃이 압도적으로 많은 노드)로 만들어야 한다.

## 핵심 설계

- 허브 노드는 `is_hub = true` 플래그로 명시적으로 지정한다
- 일반 노드: k=12 (기존)
- 허브 노드: k=100 (새 노드가 추가될 때 허브와의 연결도 추가)
- 허브를 자연 성장에 맡기지 않는다. 엉뚱한 노드가 허브 위치를 차지하는 것을 방지

## 허브 대상: 14개 (48개 시드 중)

**허브 O** — 코르카가 "누구인지":
- 코르카 정체성 (6개, intention, context_hint='정체성')
- 관계 형성 스타일 (8개, fact+intention, context_hint='관계 형성')

**허브 X** — 주제 관련 시 활성화되면 충분:
- 리서치 전문 지식 (16개) — 일반 시드 유지
- 서비스 지식 (18개) — 일반 시드 유지

## 수행할 작업

### 1. DB 마이그레이션

`supabase/migrations/00009_memory_hub_nodes.sql`:

```sql
-- is_hub 컬럼 추가
alter table memory_nodes add column is_hub boolean not null default false;

-- 정체성 + 관계 형성 노드를 허브로 지정
update memory_nodes
set is_hub = true
where conversation_id is null
  and context_hint in ('정체성', '관계 형성');
```

### 2. 도메인 타입 수정

`app/domain/memory-node.ts` — MemoryNode에 추가:
```ts
isHub: boolean;
```

### 3. node-repository.ts 수정

- `NodeRow` 인터페이스에 `is_hub: boolean` 추가
- `toNode()` 매핑에 `isHub` 추가
- `saveNodes()`에 `isHub` 파라미터 추가
- 새 함수 추가:
```ts
/** 사용자의 허브 노드 ID 목록을 조회한다. */
export async function listHubNodeIds(userId?: string): Promise<string[]>
```

### 4. network.ts — buildIncrementalNetwork 수정

핵심 변경: 새 노드 추가 시 허브 노드와의 연결을 추가로 수행

```
기존:
  새 노드 → top-12 이웃 → 양방향 엣지

변경 후:
  새 노드 → top-12 이웃 → 양방향 엣지 (기존)
          → 허브 노드 전체와 유사도 계산 → 임계값(0.2) 이상이면 양방향 엣지 추가
```

허브 노드는 14개로 고정되어 있으므로, 새 노드 추가 시 14번의 추가 유사도 계산만 필요하다. 비용 무시 가능.

구현 방식:
1. `buildIncrementalNetwork` 시작 시 `listHubNodeIds()`로 허브 ID 조회
2. 각 새 노드에 대해:
   a. 기존 로직: matchNodeNeighbors(k=12) → 양방향 엣지
   b. 추가: 허브 노드 각각과 코사인 유사도 계산 (pgvector RPC 또는 직접 계산)
   c. 유사도 > 0.2이면 양방향 엣지 추가 (이미 top-12에 포함된 허브는 스킵)
3. 결과: 허브 노드의 degree는 대화가 쌓일수록 자연스럽게 증가

### 5. seed-embeddings.ts 수정

시드 네트워크 구축 시 허브 노드에 대해서도 동일 로직 적용:
- 허브 노드는 모든 비허브 노드와 유사도 계산
- top-k (k=허브 노드의 경우 전체 비허브 노드 수, 단 임계값 0.2 이상만)로 엣지 생성

### 6. rebuildNetwork 수정

전체 재구축 시에도 허브 노드는 k를 크게 잡아야 한다:
- 일반 노드: k=12
- 허브 노드: 전체 비허브 노드와 유사도 계산, 임계값 이상 모두 연결

## 참조 파일

| 파일 | 역할 |
|------|------|
| `supabase/migrations/00007_memory_nodes_network.sql` | 현재 memory_nodes 스키마 |
| `supabase/migrations/00008_seed_memory_nodes.sql` | 48개 시드 노드 정의 |
| `app/domain/memory-node.ts` | MemoryNode 타입 |
| `app/server/memory/network.ts` | buildIncrementalNetwork, rebuildNetwork |
| `app/server/memory/node-repository.ts` | 노드/엣지 CRUD |
| `app/server/memory/activate.ts` | spreading activation (수정 불필요) |
| `scripts/seed-embeddings.ts` | 시드 임베딩 + 초기 네트워크 구축 |

## 완료 기준

- `is_hub` 컬럼이 추가되고, 정체성+관계 형성 14개 노드가 `true`
- 새 경험 노드 추가 시 허브 노드와의 연결이 자동으로 생성됨
- 허브 노드의 degree가 일반 노드보다 높음을 확인
- `activate.ts`는 수정 없이 정상 동작 (네트워크 구조만 변경)
