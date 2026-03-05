# Light House — 균일 인터페이스 아키텍처

> 상위 참조: [service-principles.md](service-principles.md)
> 설계 철학: [agentic-engineering-principles.md](../../agentic-engineering-principles.md) §모든 것은 파일이다

---

## 설계 철학

**핵심은 인터페이스다.** 다양한 대상을 하나의 인터페이스로 다룰 수 있게 만들어 시스템을 단순하게 한다.

Unix의 교훈은 "모든 것을 파일로 저장하라"가 아니라 **"read/write라는 균일한 인터페이스로 모든 것을 다뤄라"**였다. 파일은 그 인터페이스를 실현하는 추상화였을 뿐이다.

Lighthouse에서 이 인터페이스는 **문서 CRUD(생성/조회/수정/삭제)**다. 검색 결과, 분석, 메모, 논의, 종합 — 종류가 달라도 동일한 연산으로 다룬다. 문서는 이 균일한 인터페이스를 실현하는 추상화다.

**폴더도 문서다.** Unix에서 디렉토리가 "파일 목록을 담은 파일"이듯, 세션(연구 노트)도 "문서 목록을 담은 문서(collection)"다. 세션이 문서의 상위 컨테이너가 아니라, 문서의 한 종류다.

이 인터페이스가 주는 것:
- **대칭성** — 사용자와 에이전트가 동일한 인터페이스(문서 CRUD)로 상호작용한다. 누가 호출했는지만 다르다
- **조합 가능성** — 동일한 인터페이스를 가진 것들은 자유롭게 조합된다. 나란히 펼치고, 참조하고, 병합할 수 있다
- **확장 비용 최소화** — 새 기능 추가 시 인터페이스는 그대로, 타입만 추가한다. 새 저장 경로, 새 스토어, 새 hydration이 불필요하다

---

## Document 모델

> 원본: `app/domain/document.ts`

```ts
interface Document {
  id: string;
  type: DocumentType;
  title: string;
  content: string;              // 마크다운 본문
  createdBy: "user" | "agent";
  metadata: DocumentMetadata;   // 타입별 구조화된 데이터
  refs: string[];               // 참조하는 다른 문서 ID
  conversationId: string;
  createdAt: string;
  updatedAt: string;
}

type DocumentType =
  | "search"      // 검색 결과
  | "analysis"    // 논문 분석
  | "synthesis"   // 종합 분석
  | "memo"        // 사용자 메모
  | "discussion"  // 대화/논의
  | "overview"    // 연구 지형 개관
  | "collection"; // 문서 목록 (세션 = collection 문서)
```

### 타입별 metadata

```ts
type DocumentMetadata =
  | SearchMetadata      // { type, query, papers[], total }
  | AnalysisMetadata    // { type, paperId, paper, analysis, source: "pdf" | "abstract" }
  | SynthesisMetadata   // { type, topicName, paperIds[], sections[] }
  | MemoMetadata        // { type: "memo" }
  | DiscussionMetadata  // { type, messages[] }
  | OverviewMetadata    // { type, clusters[], landscapeOverview }
  | CollectionMetadata; // { type, childIds[] }
```

### collection — 폴더도 문서다

```ts
interface CollectionMetadata {
  type: "collection";
  childIds: string[];  // 하위 문서 ID 목록 (순서 보장)
}
```

- 세션(연구 노트) = collection 문서. `childIds`에 하위 문서 ID
- 중첩 가능 (collection 안에 collection)
- `childIds`는 소유 관계, `refs`는 참조 관계 — 의미 분리
- collection 생성 시 대응 conversation 행도 함께 생성 (messages, memory FK 보존)
- 구현 프롬프트: `collection-document-prompt.md`

---

## 에이전트 도구 → 문서 연산

모든 도구가 동일한 인터페이스(문서 CRUD)를 통해 결과를 반환한다.

| 도구 | 연산 | 결과 |
|------|------|------|
| search_papers | `createDocument("search", ...)` | 검색 결과 문서 |
| analyze_papers | `createDocument("analysis", ...)` | 분석 문서 (논문당 1개) |
| cluster_papers | `createDocument("overview", ...)` | 연구 지형 문서 |
| synthesize_topic | `createDocument("synthesis", ...)` | 종합 분석 문서 |

도구 구현 패턴 (`app/strategies/document-creation.ts`):

```ts
TOOL_DOCUMENT_TYPE_MAP: {
  search_papers: "search",
  analyze_papers: "analysis",
  evaluate_importance: "analysis",
  cluster_papers: "overview",
  synthesize_topic: "synthesis",
  find_related_papers: "search",
  translate_abstract: "analysis",
}
```

새 도구를 추가할 때: DocumentType 하나 추가 + metadata 타입 정의 + TOOL_DOCUMENT_TYPE_MAP 엔트리. 새 스토어, 새 슬라이스, 새 영속 경로가 불필요하다.

---

## 사용자 행동 — 에이전트와 동일한 인터페이스

인터페이스가 균일하기 때문에, 사용자도 에이전트와 동일한 연산(문서 CRUD)으로 참여한다.

| 사용자 행동 | 연산 | API |
|------------|------|-----|
| 논문 검색 | `createDocument("search", { createdBy: "user" })` | `POST /api/documents/search` |
| 메모 작성 | `createDocument("memo", { createdBy: "user" })` | `POST /api/documents` |
| 문서 제목 편집 | `updateDocument(id, { title })` | `PATCH /api/documents/:id` |
| 문서 삭제 | `deleteDocument(id)` | `DELETE /api/documents/:id` |
| 검토 완료 마킹 | reviewed_papers upsert | `POST /api/papers/reviewed` |
| 검토 해제 | reviewed_papers 삭제 | `DELETE /api/papers/reviewed` |

차이는 **호출자(createdBy)**뿐이다. 에이전트가 만든 검색 문서와 사용자가 만든 검색 문서는 동일한 타입, 동일한 렌더링, 동일한 저장 경로를 탄다.

---

## 워크스페이스

```
/chat/[conversationId]
```

단일 페이지에서 여러 문서를 나란히 펼친다. 연구 흐름이 자유롭다.

### 웹 계약 — 워크스페이스 모델

워크스페이스 모델(VS Code, Figma, Notion)의 기준:

**1. 주소 계약**
- URL = **워크스페이스 식별자** (`/chat/[conversationId]`)
- 새로고침 시 세션이 복원되면 계약 충족
- 개별 문서는 워크스페이스 내부 상태

**2. 히스토리 계약**
- 세션 전환만 히스토리. 문서 열기/닫기는 히스토리에 넣지 않음

**3. 복원 계약**
- 세션(문서 컬렉션) 복원. 열린 패널 배치는 복원하지 않아도 됨

```
┌─────────────────────────────────────────────────────────────────┐
│ 사이드바        │ 문서 패널 1          │ 문서 패널 2             │
│                 │                      │                        │
│ 📄 검색: RLHF  │ [검색: RLHF safety]  │ [분석: Attention Is...] │
│ 📄 분석: Att.. │                      │                        │
│ 📄 개관: 연구..│ • Attention Is...    │ ## 요약                │
│ 📄 메모: 내 ..│ • BERT               │ self-attention 메커...  │
│ 📄 종합: 안전..│ • InstructGPT        │                        │
│                 │                      │ ## 방법론               │
│ [🔍 검색]      │ [검색바]             │ ...                    │
│ [✏️ 메모]      │                      │                        │
└─────────────────────────────────────────────────────────────────┘
```

### 사이드바 (`app/components/Sidebar.tsx`)

- collection 문서 목록 (= 세션 목록)
- 현재 세션 문서 목록 (타입별 아이콘, 클릭 시 scrollIntoView)
- 문서 생성 버튼 (🔍 새 검색, ✏️ 새 메모)

### 문서 패널 (`app/components/workspace/DocumentStrip.tsx`)

- flex + snap-x snap-mandatory 수평 스크롤로 다중 문서 나란히 표시
- 2타일 고정 레이아웃: 문서 1개면 100% 폭, 2개 이상이면 각 50% 폭
- IntersectionObserver로 가시 문서 추적
- 새 문서 추가 시 자동 스크롤
- 각 패널 헤더: 아이콘 + 제목(더블클릭 편집) + 닫기 버튼
- discussion 문서는 닫기 불가 (첫 번째 패널에 고정)

### 대화 통합

대화(discussion)도 문서다. 에이전트 응답 중에 생성된 다른 문서(검색, 분석)가 워크스페이스에 자동으로 추가된다 (`TileWorkspace`가 tool invocation 모니터링).

---

## 상태 관리

```
workspaceStore    — Document[] (문서 CRUD, 열린 패널, 가시성 추적)
agentStore        — 에이전트 FSM 상태 (idle, executing, awaiting_approval)
```

### workspaceStore (`app/stores/workspace-store.ts`)

| 상태 | 설명 |
|------|------|
| `documents` | 현재 세션의 문서 배열 (`Document[]`) |
| `visibleDocIds` | 화면에 보이는 문서 ID |
| `currentConversationId` | 현재 대화 ID |
| `sidebarCollapsed` | 사이드바 접힘 여부 |

| 액션 | 설명 |
|------|------|
| `addDocument(doc, position?)` | 문서 추가 (같은 ID면 업데이트) |
| `removeDocument(docId)` | 문서 제거 (첫 번째 문서 보호) |
| `updateDocument(docId, updates)` | title, content, updatedAt 갱신 |
| `setDocuments(docs)` | 초기 hydration |

---

## 렌더링 — 타입별 컴포넌트 + 공통 패널

> 원본: `app/strategies/rendering.ts`

| 타입 | 아이콘 | 컴포넌트 | 주요 인터랙션 |
|------|--------|---------|-------------|
| search | 🔍 | SearchDocument | 검색바 (재검색), 자동 일괄 분석, 검토완료 체크박스, PDF 링크 |
| analysis | 📊 | AnalysisDocument | 마크다운 렌더링, 원문 링크, 소스 배지 (전문/초록) |
| synthesis | 📝 | SynthesisDocument | 마크다운 렌더링 |
| memo | ✏️ | MemoDocument | 제목/내용 인라인 편집, 디바운스 PATCH |
| discussion | 💬 | ConversationDocument | 메시지 입력, 에이전트 응답 스트리밍 |
| overview | 🗺️ | OverviewDocument | 마크다운 렌더링 |
| collection | 📁 | CollectionDocument | 하위 문서 목록, 문서 열기, 순서 변경 |

새 문서 타입 추가 = 컴포넌트 하나 + RENDERING_SPECS 엔트리 + DocumentRenderer switch case. 스토어, 영속 경로, hydration 변경 불필요.

---

## 영속 전략

### 서버 DB (Supabase)

```
documents 테이블 — 문서 단위 행
  id, conversation_id, type, title, content,
  created_by, metadata (jsonb), refs (text[]),
  created_at, updated_at
```

### API 라우트

```
POST   /api/documents              — 문서 생성 (사용자 직접 or 도구 결과)
GET    /api/documents/:id          — 문서 조회
PATCH  /api/documents/:id          — 문서 갱신 (제목, 내용)
DELETE /api/documents/:id          — 문서 삭제
GET    /api/documents?conversationId=:id  — 세션 문서 목록

POST   /api/documents/search       — 사용자 직접 검색 → Document(search) 생성
POST   /api/documents/analyze      — 단일 논문 분석 (S2 fetch + PDF/초록 분석)
POST   /api/documents/analyze/batch — 일괄 분석 (검토 마킹 생략)

GET    /api/collections            — collection 문서 목록
POST   /api/collections            — 새 collection 생성 (+ conversation + discussion)

GET    /api/papers/reviewed        — 검토한 논문 전체 목록
POST   /api/papers/reviewed        — 검토 완료 마킹
DELETE /api/papers/reviewed        — 검토 해제
```

---

## 개발 방법론: 삼분법

| 관점 | 역할 | 위치 | 형태 |
|------|------|------|------|
| **원칙 (Principles)** | 에이전트가 판단할 때 참조하는 기준. 프롬프트에 주입된다 | `app/principles/*.ts` | 코드 (함수로 export) |
| **전략 (Strategy)** | 코드가 수행하는 구현 방법. 원칙을 참조한다 | `app/strategies/*.ts` | 코드 (구현 로직) |
| **인터페이스 (Interface)** | 입출력 계약. 코드 자체가 명세다 | `app/domain/*.ts` | 타입 정의 |

### .md/.ts 이중화 기준

**원본이 하나**여야 한다:

| 대상 | .md | .ts | 이유 |
|------|:---:|:---:|------|
| 서비스 대원칙 | O | — | 인간이 읽는 철학. 코드 주입 불필요 |
| 아키텍처 결정 | O | — | 설계 근거. 코드가 아닌 문서 |
| 도구/시나리오 원칙 | — | O | 프롬프트에 주입. 코드가 원본 |
| 인터페이스 정의 | — | O | 코드 자체가 명세 |
| 동기화 규칙 | O (AGENTS.md) | — | 에이전트 행동 지침 |

---

## 보존하는 것

- **service-principles.md** — 대원칙, 동료 원칙 4가지, 에이전트 계층 구조
- **자율성 5단계 (L1~L5)** — 도구별 자율성 수준 유지
- **FSM 패턴** — 도구 실행 단위로 적용 (agentStore)
- **3-Phase Turn Pipeline** — 대화 오케스트레이션 구조 유지
- **기억 시스템** — memory_nodes 네트워크, spreading activation

---

## 검증 기준

1. **인터페이스 균일성** — 모든 도구 출력, 사용자 행동, 저장, 렌더링이 동일한 인터페이스(문서 CRUD)를 통과한다
2. **확장 비용** — 새 도구 추가 = DocumentType 1개 + metadata 타입 + 컴포넌트. 인터페이스 변경 없음
3. **대칭성** — 사용자와 에이전트가 동일한 인터페이스로 참여한다 (`createdBy`만 다르다)
4. **자유도** — 종합 분석 중에 새 검색을 시작할 수 있다. 인터페이스가 같으니 조합이 자유롭다
5. **단순성** — 2개 스토어 (workspaceStore + agentStore), 하나의 인터페이스 (Document)
