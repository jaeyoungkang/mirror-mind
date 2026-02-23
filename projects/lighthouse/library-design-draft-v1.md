# Light House UI 재설계 — Research Library + 동료 보조

## Context

Board+Graph 패널을 제거한 뒤, 남은 탭 플레이스홀더를 새로운 방향으로 채운다.
핵심 전환: "논문을 사용자가 수동 관리" → "연구 동료가 보조하는 라이브러리에서 보고 정리하기"

현재 상태:
- `NotebookShell.tsx`에 Board/Graph 플레이스홀더 탭이 남아있다
- 논문은 `artifacts` 테이블의 `paper_card` 타입으로 대화별로 저장
- `/api/papers` 엔드포인트가 전체 논문 flat 리스트를 반환
- 7개 도구(search, analyze, evaluate, cluster, synthesize, translate, propose)
- 경험 기억(research_journeys)이 세션 간 맥락 유지

## 설계 범위

이 문서는 **설계**만 다룬다. 구현은 별도 단계에서 진행.

---

## 1. Notebook과 Library의 역할 분담

| | Notebook | Library |
|---|---|---|
| **핵심 역할** | 동료와 탐색·분석·대화 | 논문을 보고 정리 |
| **상호작용** | 대화 입력, 제안 카드 응답 | 태그 편집, 컬렉션 관리, 필터/정렬 |
| **동료의 존재** | 대화 상대로 직접 등장 | 자동 태깅, 메모 등 결과물만 보임 |
| **인사이트** | 갭 분석, 연결 발견, 방향 제안 | 없음 (Notebook에서만) |
| **논문 생성** | 검색·분석 도구로 생성 | 생성 없음 |
| **논문 정리** | 동료에게 요청 가능 (자연어) | 직접 UI 조작 (태그, 컬렉션, 별표) |

핵심: Library는 "대화 없는 관리 도구", Notebook은 "관리 없는 대화 인터페이스".
둘이 같은 데이터를 다른 관점에서 본다.

---

## 2. 내비게이션 변경

### 탭 구조

```
[Notebook]  [Library]
```

- Board, Graph 탭을 **Library** 단일 탭으로 교체
- `NotebookShell.tsx`의 `ViewTab`을 `"notebook" | "library"`로 변경
- 플레이스홀더 컴포넌트 2개 삭제

### 양방향 내비게이션

- **Library → Notebook**: 논문 카드의 "출처 대화" 링크 → 해당 대화의 아티팩트로 스크롤
- **Notebook → Library**: 아티팩트 블록에 "라이브러리에서 보기" 링크 → Library 탭 전환 + 해당 논문 하이라이트

---

## 3. Library View 설계

### 레이아웃

```
+-----------------------------------------------------------+
| Light House    [Notebook]  [Library]                       |
+-----------------------------------------------------------+
|                                                            |
| [검색]  [Confidence ▾] [년도 ▾]   그룹: 맥락별 ▾         |
|                                     정렬: 최신순 ▾ [≡][⊞] |
|                                                            |
| ── Transformer 추천 다양성 (2/23) ────────── 12편 ──────  |
| ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        |
| │ ★ Chen 2024  │ │ Wang 2024    │ │ Kim 2024     │        |
| │ Contrastive  │ │ Multi-obj..  │ │ Adaptive..   │        |
| │ NeurIPS [H]  │ │ ICML    [M]  │ │ AAAI    [H]  │        |
| │ 127 citations│ │ 89 citations │ │ 45 citations │        |
| │ #diversity   │ │ #pareto      │ │ #attention   │        |
| │ ✎ edit tags  │ │              │ │              │        |
| │              │ │              │ │              │        |
| │ corca: 이 분 │ │              │ │              │        |
| │ 야의 핵심 논문│ │              │ │              │        |
| └──────────────┘ └──────────────┘ └──────────────┘        |
|                                                            |
| ── RLHF 안전성 (2/22) ─────────────────── 8편 ──────────  |
| ┌──────────────┐ ┌──────────────┐                          |
| │ Lee 2024     │ │ Park 2025    │ ...                      |
| └──────────────┘ └──────────────┘                          |
|                                                            |
+-----------------------------------------------------------+
```

### 논문 카드 (카드 뷰, 기본)

보이는 정보:
- **★ 별표** 토글 (카드 좌상단, 클릭으로 토글)
- **제목** + 첫 번째 저자 + 년도
- **Confidence 뱃지** (H/M/L, 기존 색상 코드)
- **학회/저널** + **인용수**
- **태그** (상위 3개) + 태그 편집 아이콘 (✎)
- **corca 메모** (있을 경우, 1~2줄)
- **출처 대화** 링크 (카드 하단)

카드에서 직접 가능한 조작:
- ★ 별표 토글
- 태그 편집 (인라인 태그 에디터: 추가/삭제)
- 카드 클릭 → 상세 패널

### 테이블 뷰 (토글)

| ★ | 제목 | 저자 | 년도 | 인용 | Conf | 태그 | 출처 |
|---|------|------|------|------|------|------|------|

- 열 헤더 클릭으로 정렬
- 행 클릭 → 상세 패널
- ★ 열에서 직접 별표 토글

### 그루핑

기본값: **연구 맥락별** (= 대화 제목 + 날짜)

추가 그루핑:
- **태그별** — 대화 경계를 넘어 같은 주제의 논문이 모인다
- **시간순** — 주/월 단위
- **컬렉션별** — 동료 또는 사용자가 만든 그룹
- **별표만** — 별표 표시된 논문만 필터

### 필터링

- 텍스트 검색 (제목, 저자, 키워드, AI 요약)
- Confidence 레벨 (H/M/L 체크박스)
- 년도 범위
- 대화 필터 (특정 세션의 논문만)

### 카드 상세 패널 (슬라이드오버)

카드 클릭 → 우측에서 슬라이드오버:
- 기존 `PaperCard` 컴포넌트의 상세 정보 (AI 분석, 근거, 키워드)
- **태그 편집** 영역 (추가/삭제)
- **corca 메모** 전체 표시
- **컬렉션** — 이 논문이 속한 컬렉션 목록 + 다른 컬렉션에 추가
- **"대화에서 보기"** 버튼 → Notebook 탭 전환 + 스크롤
- **논문 원문 링크** (외부)

### 컬렉션 관리 UI

Library 상단 또는 사이드바에 컬렉션 섹션:

```
컬렉션
├ Diversity in RecSys (8편) — corca가 생성
├ RLHF Safety (7편) — corca가 생성
└ [+ 새 컬렉션]
```

- 컬렉션 클릭 → 해당 컬렉션 논문만 필터
- 컬렉션은 동료가 대화에서 생성하거나, 사용자가 Library에서 직접 생성
- 논문을 컬렉션에 추가: 상세 패널에서 또는 카드 드래그(선택적)

---

## 4. 동료의 라이브러리 역할

### 원칙

동료는 Library UI를 직접 조작하지 않는다. 대신:
1. 분석 시 **자동 태깅** (L5, 조용히)
2. 대화 중 **메모 생성** (L5, 중요한 관찰을 artifact에 기록)
3. 대화에서 **컬렉션 생성 제안** (L3, propose로 제안 후 승인 시 생성)
4. **라이브러리 인사이트**는 Notebook 대화에서만 제공

### 새 도구: `organize_library`

기존 7개 도구에 1개 추가:

```
organize_library
  - action: "tag" | "annotate" | "collect"
  - artifactIds: string[]
  - tags?: string[]           (action=tag)
  - annotation?: string       (action=annotate)
  - collectionName?: string   (action=collect)
  - collectionDescription?: string
```

자율성:
- `tag`: **L5** — 분석 키워드 기반, 되돌림 비용 없음
- `annotate`: **L5** — 부가 정보, 비파괴적
- `collect`: **L3** — 그루핑 기준이 사용자 멘탈 모델에 의존, propose 후 실행

### 라이브러리 맥락 주입

`buildSystemPrompt()`에 라이브러리 요약을 추가 주입:

```
## 라이브러리 현황
- 총 20편, 3개 세션
- 주요 주제: Transformer 추천 다양성(12편), RLHF 안전성(8편)
- 최근 추가: Park 2025 "Safe RLHF..." (2시간 전)
- 컬렉션: Diversity in RecSys(8편), RLHF Safety(7편)
```

동료가 도구 호출 없이도 라이브러리를 인지하고, 대화에서 자연스럽게 참조.

### 자동 태깅

`analyze_papers` 실행 시 `analysis.keywords`를 아티팩트의 `tags` 칼럼에 자동 복사.
별도 도구 호출 불필요.

### 동료의 선제적 행동 (Notebook에서)

| 트리거 | 동료 행동 | 자율성 |
|--------|----------|--------|
| 분석 완료, 다른 세션에 같은 논문 존재 | "이 논문은 지난 [세션명]에서도 본 적 있어요" | L5 |
| 라이브러리 10편 이상 & 컬렉션 없음 | propose로 "정리해볼까요?" 제안 | L3 |
| 같은 저자 3편 이상 | "이 저자의 연구 궤적이 보여요" 언급 | L5 |
| 분석 논문들에서 공통 한계 발견 | 갭 인사이트를 대화에서 제시 | L4 |
| 라이브러리에 특정 관점 부재 | "이 방향의 논문이 빠져 있어요" 제안 | L3 |

---

## 5. 탐색 시나리오 고도화

### 현재 흐름의 한계

```
사용자: "X 찾아줘" → 검색 → 분석 → 클러스터링 → 종합
```

일방적. 동료가 축적된 라이브러리를 활용하지 못한다.

### 개선된 흐름

**시나리오 1: 돌아온 연구자**
```
사용자: (새 세션) "attention mechanism 논문 탐색하고 싶어"

동료: (라이브러리 요약 인지)
  "지난번 Transformer 추천 시스템 연구에서 attention 관련 논문을
   5편 분석했었어요. 그중 Chen 2024가 이번 주제와도 연결될 수 있는데,
   거기서 이어갈까요, 아니면 새로 시작할까요?"
```

**시나리오 2: 갭 탐지**
```
동료: (분석 완료 후)
  "지금까지 20편을 봤는데, 전부 Transformer 기반이에요.
   비교를 위해 GNN 기반 접근도 한번 찾아볼까요?"
  [GNN 기반 탐색하기] [지금은 괜찮아요]
```

**시나리오 3: 라이브러리 정리**
```
사용자: "지금까지 모은 논문 정리해줘"

동료: organize_library(action="collect") 제안 →
  "3개 세션에서 모은 20편을 주제별로 정리해볼게요:
   - 'Diversity in RecSys' (8편)
   - 'RLHF Safety' (7편)
   - 'Attention Variants' (5편)
   이렇게 묶어둘까요?"
  [이대로 저장] [다른 기준으로] [직접 조정할게]
```

**시나리오 4: 교차 세션 연결**
```
동료: (새 세션에서 분석 중)
  "흥미로운 연결이 있어요. Kim 2025가
   지난 RLHF 연구에서 봤던 Lee 2024를 인용하고 있네요.
   두 분야를 잇는 다리 역할을 할 수 있어요."
```

### 핵심: 동료는 라이브러리를 "안다"

라이브러리 요약이 시스템 프롬프트에 주입되므로:
- 사용자가 어떤 논문을 봤는지 안다
- 어떤 주제를 탐색했는지 안다
- 빠진 관점을 짚을 수 있다
- 세션 간 연결을 만들 수 있다

---

## 6. 데이터 모델 변경

### artifacts 테이블 확장

```sql
ALTER TABLE artifacts
  ADD COLUMN tags text[] NOT NULL DEFAULT '{}',
  ADD COLUMN companion_note text,
  ADD COLUMN is_starred boolean NOT NULL DEFAULT false;

CREATE INDEX idx_artifacts_tags ON artifacts USING gin(tags);
CREATE INDEX idx_artifacts_starred ON artifacts(is_starred) WHERE is_starred = true;
```

- `tags`: 키워드 태그 배열. 분석 시 자동 + 사용자/동료가 추가
- `companion_note`: 동료가 대화 맥락에서 남긴 메모
- `is_starred`: 사용자의 별표 표시

### 새 테이블: collections

```sql
CREATE TABLE collections (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL,
  name            text NOT NULL,
  description     text NOT NULL DEFAULT '',
  artifact_ids    uuid[] NOT NULL DEFAULT '{}',
  created_by      text NOT NULL DEFAULT 'companion'
                  CHECK (created_by IN ('user', 'companion')),
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_collections_user_id ON collections(user_id);
```

- 대화에 종속되지 않는 교차 세션 그룹
- RLS로 사용자별 격리

### 도메인 타입

```typescript
// domain/collection.ts
interface Collection {
  id: string;
  userId: string;
  name: string;
  description: string;
  artifactIds: string[];
  createdBy: "user" | "companion";
  createdAt: string;
  updatedAt: string;
}
```

### API 확장

- `GET /api/papers` 확장 — tags, companion_note, is_starred 포함
- `GET /api/collections` — 컬렉션 목록
- `POST /api/collections` — 컬렉션 생성
- `PATCH /api/collections/:id` — 컬렉션 수정 (논문 추가/제거)
- `PATCH /api/papers/:id` — 태그, 별표, 메모 업데이트 (단일 엔드포인트)

---

## 7. 시스템 프롬프트 확장

`buildSystemPrompt()`에 라이브러리 섹션 추가:

```typescript
export function buildSystemPrompt(
  memorySection?: string,
  isFirstVisit?: boolean,
  librarySection?: string,  // 새로 추가
): string {
  let prompt = BASE_SYSTEM_PROMPT;
  if (isFirstVisit) prompt += FIRST_VISIT_SECTION;
  if (librarySection) prompt += "\n" + librarySection;
  if (memorySection) prompt += "\n" + memorySection;
  return prompt;
}
```

라이브러리 섹션은 chat API에서 동적 생성:
- 총 논문 수, 세션 수
- 주요 주제 (태그 빈도 상위 5개)
- 최근 추가 논문 3건
- 컬렉션 목록 (있으면)
- 별표 논문 목록

시스템 프롬프트에 `organize_library` 도구 사용 규칙 추가:
- tag/annotate는 자연스럽게 대화 중 수행 (L5)
- collect는 propose 후 승인 시 실행 (L3)

---

## 8. 설계 문서 업데이트 대상

이 설계가 확정되면 lighthouse 저장소의 다음 문서를 업데이트:

- **SPEC.md** §4-5: Board+Graph → Library 뷰 교체, 역할 분담표, 레이아웃 명세
- **architecture.md**: organize_library 도구, 라이브러리 맥락 주입 흐름, collections 데이터 모델
- **state-management.md**: Library 뷰 UI 상태 (필터, 정렬, 그루핑, 활성 컬렉션)
- **conventions.md**: 컬렉션 타입, 태그 규칙, API 경로 규칙

---

## 9. 구현 순서 (참고)

1. **데이터 모델** — 마이그레이션 + 도메인 타입 + 리포지토리
2. **Library 뷰** — 탭 교체, 카드/테이블 뷰, 필터/정렬/그루핑
3. **직접 조작** — 별표 토글, 태그 편집, 컬렉션 관리 UI
4. **상세 패널** — 슬라이드오버, 컬렉션 할당, 대화 링크
5. **Notebook↔Library 연결** — 양방향 내비게이션
6. **organize_library 도구** — 동료의 자동 태깅, 메모, 컬렉션 생성
7. **라이브러리 맥락 주입** — 시스템 프롬프트 확장
8. **동료 선제적 행동** — 교차 세션 감지, 갭 분석, 정리 제안
