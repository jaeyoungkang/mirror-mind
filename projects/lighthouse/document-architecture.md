# Light House 재설계 — 균일 인터페이스 아키텍처

> 상위 참조: [shared-tools-design.md](shared-tools-design.md), [service-principles.md](service-principles.md)
> 설계 철학: [agentic-engineering-principles.md](../../agentic-engineering-principles.md) §모든 것은 파일이다

---

## 설계 철학

**핵심은 인터페이스다.** 다양한 대상을 하나의 인터페이스로 다룰 수 있게 만들어 시스템을 단순하게 한다.

Unix의 교훈은 "모든 것을 파일로 저장하라"가 아니라 **"read/write라는 균일한 인터페이스로 모든 것을 다뤄라"**였다. 파일은 그 인터페이스를 실현하는 추상화였을 뿐이다.

Lighthouse에서 이 인터페이스는 **문서 CRUD(생성/조회/수정/삭제)**다. 검색 결과, 분석, 메모, 논의, 종합 — 종류가 달라도 동일한 연산으로 다룬다. 문서는 이 균일한 인터페이스를 실현하는 추상화다.

이 인터페이스가 주는 것:
- **대칭성** — 사용자와 에이전트가 동일한 인터페이스(문서 CRUD)로 상호작용한다. 누가 호출했는지만 다르다
- **조합 가능성** — 동일한 인터페이스를 가진 것들은 자유롭게 조합된다. 나란히 펼치고, 참조하고, 병합할 수 있다
- **확장 비용 최소화** — 새 기능 추가 시 인터페이스는 그대로, 타입만 추가한다. 새 저장 경로, 새 스토어, 새 hydration이 불필요하다

---

## 현재 구조의 문제

### 1. Phase 중심의 선형 흐름

```
현재: Phase 1(검색) → Phase 2(이해) → Phase 3(확장) → Phase 4(심화)
```

연구는 선형이 아니다. 심화 중에 새 검색이 필요하고, 검색 중에 메모를 남기고 싶다. Phase 구조가 이를 가로막는다.

### 2. 도구별 다른 출력 형태

| 도구 | 현재 출력 | 저장 위치 |
|------|----------|----------|
| search_papers | PaperCore[] | session.search.resultByQueryKey |
| analyze_papers | AIAnalysis | session.aiAnalysis.byPaperId |
| cluster_papers | ClusteringResult | session.researchGuide.clusteringByQueryKey |
| synthesize_topic | TopicSynthesis | session.topicSynthesis.byTopicName |

도구마다 인터페이스가 다르다. 타입이 다르고, 저장 경로가 다르고, 렌더링이 다르다. 새 도구를 추가할 때마다 새로운 슬라이스, 새로운 스토어, 새로운 컴포넌트가 필요하다. **인터페이스가 통일되지 않은 것이 복잡성의 근본 원인이다.**

### 3. 에이전트만 도구를 쓴다

사용자는 대화로만 참여한다. 검색, 분석, 정리 모두 에이전트를 통해서만 가능하다. 이건 동료가 아니라 비서 구조다.

### 4. 8개 스토어의 복잡성

sessionStore, searchStore, analysisStore, importanceStore, researchGuideStore, topicStore, workflowStore, translationStore — 각각 다른 패턴, 다른 hydration 로직, 다른 영속 경로. orchestrator.ts가 이들을 조율하는데 이미 복잡하다.

---

## 핵심 변경: 균일한 인터페이스, 문서라는 추상화

### Document 모델

```ts
interface Document {
  id: string;
  type: DocumentType;
  title: string;
  content: string;              // 마크다운 본문
  createdBy: "user" | "agent";
  metadata: DocumentMetadata;   // 타입별 구조화된 데이터
  refs: string[];               // 참조하는 다른 문서 ID
  sessionId: string;
  createdAt: string;
  updatedAt: string;
}

type DocumentType =
  | "search"      // 검색 결과
  | "analysis"    // 논문 분석
  | "synthesis"   // 종합 분석
  | "memo"        // 사용자 메모
  | "discussion"  // 대화/논의
  | "overview";   // 연구 지형 개관
```

### 타입별 metadata

```ts
type DocumentMetadata =
  | SearchMetadata
  | AnalysisMetadata
  | SynthesisMetadata
  | MemoMetadata
  | DiscussionMetadata
  | OverviewMetadata;

interface SearchMetadata {
  query: string;
  papers: PaperCore[];          // 검색된 논문 목록
  total: number;
}

interface AnalysisMetadata {
  paperId: string;
  paper: PaperCore;
  analysis: AIAnalysis;         // 기존 구조화된 분석 데이터 유지
}

interface SynthesisMetadata {
  topicName: string;
  paperIds: string[];           // 분석 대상 논문
  sections: SynthesisSection[]; // 구조화된 섹션 데이터
}

interface MemoMetadata {}       // 순수 마크다운, 추가 구조 없음

interface DiscussionMetadata {
  messages: Message[];          // 대화 이력
}

interface OverviewMetadata {
  clusters: Cluster[];
  landscapeOverview: string;
}
```

### 균일한 인터페이스

모든 문서는 동일한 연산을 지원한다:

```ts
interface DocumentStore {
  // CRUD
  create(type: DocumentType, params: CreateParams): Document;
  update(id: string, changes: Partial<Document>): Document;
  delete(id: string): void;
  get(id: string): Document | null;

  // 조회
  list(filter?: { type?: DocumentType; sessionId?: string }): Document[];
  search(query: string): Document[];  // 문서 내 전문 검색

  // 워크스페이스
  open(id: string): void;      // 패널에 문서 열기
  close(id: string): void;     // 패널에서 닫기
  focus(id: string): void;     // 포커스 이동
}
```

---

## 에이전트 도구 → 문서 연산

모든 도구가 동일한 인터페이스(문서 CRUD)를 통해 결과를 반환한다.

### 도구 재정의

| 도구 | 연산 | 결과 |
|------|------|------|
| search_papers | `documentStore.create("search", ...)` | 검색 결과 문서 |
| analyze_papers | `documentStore.create("analysis", ...)` | 분석 문서 (논문당 1개) |
| cluster_papers | `documentStore.create("overview", ...)` | 연구 지형 문서 |
| synthesize_topic | `documentStore.create("synthesis", ...)` | 종합 분석 문서 |
| update_research_panel | `documentStore.update(id, ...)` | 기존 문서 갱신 |

### 도구 구현 패턴 통일

```ts
// 모든 도구가 따르는 공통 패턴
async function executeTool(params: ToolParams): Promise<Document> {
  // 1. 외부 API 또는 LLM 호출
  const result = await callExternal(params);

  // 2. 마크다운 본문 생성
  const content = renderMarkdown(result);

  // 3. 문서 생성 (단일 경로)
  return documentStore.create(params.type, {
    title: generateTitle(params),
    content,
    metadata: result,
    createdBy: "agent",
    refs: params.refs ?? [],
  });
}
```

새 도구를 추가할 때: DocumentType 하나 추가 + metadata 타입 정의 + executeTool 패턴 따르기. 새 스토어, 새 슬라이스, 새 영속 경로가 불필요하다.

---

## 사용자 행동 — 에이전트와 동일한 인터페이스

인터페이스가 균일하기 때문에, 사용자도 에이전트와 동일한 연산(문서 CRUD)으로 참여한다.

| 사용자 행동 | 연산 |
|------------|------|
| 검색 실행 | `documentStore.create("search", { query })` |
| 메모 작성 | `documentStore.create("memo", { content })` |
| 문서 편집 | `documentStore.update(id, { content })` |
| 문서에 코멘트 | `documentStore.update(id, { ... })` |

차이는 **호출자(createdBy)**뿐이다. 에이전트가 만든 검색 문서와 사용자가 만든 검색 문서는 동일한 타입, 동일한 렌더링, 동일한 저장 경로를 탄다.

---

## 워크스페이스 — Phase를 대체하는 구조

### 현재: Phase 기반 페이지 전환

```
/(홈)                           → Phase 1-2 (검색+이해)
/explore/[sessionId]            → Phase 3 (확장)
/explore/[sessionId]/topic/[t]  → Phase 4 (심화)
```

### 변경: 워크스페이스

```
/workspace/[sessionId]
```

단일 페이지에서 여러 문서를 나란히 펼친다. 연구 흐름이 자유롭다.

### 웹 계약 재정의 — 페이지 모델에서 워크스페이스 모델로

기존 state-management.md의 웹 개발 기준 7가지는 페이지 기반 모델을 전제한다. 워크스페이스 모델(VS Code, Figma, Notion)에서는 4개 기준을 재정의한다.

**1. 주소 계약**
- ~~URL = 페이지 식별자~~ → URL = **워크스페이스 식별자**
- `/workspace/[sessionId]`가 리소스. 새로고침 시 세션이 복원되면 계약 충족
- 개별 문서는 워크스페이스 내부 상태. URL로 식별할 필요 없음

**2. 히스토리 계약**
- ~~페이지 전환 = 히스토리 엔트리~~ → **워크스페이스 진입/이탈만 히스토리**
- 문서 열기/닫기는 히스토리에 넣지 않음 (VS Code에서 파일 열 때마다 뒤로가기가 쌓이지 않듯)
- 세션 전환, 워크스페이스 나가기만 push

**3. 복원 계약**
- ~~모든 상태 복원~~ → **세션(문서 컬렉션) 복원**
- 새로고침 시: 세션의 모든 문서가 사이드바에 존재. 열린 패널 배치는 복원하지 않아도 됨
- 워크스페이스 앱의 관례: 파일은 보존, 에디터 탭 배치는 초기화되어도 수용 가능

**7. 반패턴 신호**
- ~~URL 안 바뀌는데 컨텍스트 바뀜 = 반패턴~~ → 워크스페이스 모델에서는 정상
- 새로운 반패턴: **세션 ID가 URL에 없는데 세션 데이터가 바뀜**, **새로고침 시 세션이 사라짐**

**변경 없음: 4(HTTP 의미론), 5(상태 경계), 6(관측 가능성)** — 보편적 원칙이므로 그대로 유지.

```
┌─────────────────────────────────────────────────────────────────┐
│ 사이드바        │ 문서 패널 1          │ 문서 패널 2             │
│                 │                      │                        │
│ 📄 검색: RLHF  │ [검색: RLHF safety]  │ [분석: Attention Is...] │
│ 📄 분석: Att.. │                      │                        │
│ 📄 개관: 연구..│ • Attention Is...    │ ## 요약                │
│ 📄 메모: 내 ..│ • BERT               │ self-attention 메커...  │
│ 📄 종합: 안전..│ • InstructGPT        │                        │
│ 💬 논의        │                      │ ## 방법론               │
│                 │ [검색바]             │ ...                    │
│ [+ 새 문서]    │                      │                        │
└─────────────────────────────────────────────────────────────────┘
```

### 사이드바

- 세션 내 모든 문서 목록 (타입별 아이콘)
- 문서 생성 버튼 (메모, 검색)
- 드래그로 패널에 열기

### 문서 패널

- 1~3개 문서를 나란히 표시 (react-resizable-panels 활용)
- 각 문서는 동일한 렌더러: 마크다운 본문 + 타입별 인터랙션
- 문서 간 참조 링크 (refs) 클릭으로 문서 이동

### 대화 통합

대화(discussion)도 문서다. 별도의 "채팅 영역"이 아니라, 논의 문서를 열어서 에이전트와 대화한다. 에이전트 응답 중에 생성된 다른 문서(검색, 분석)가 워크스페이스에 자동으로 추가된다.

```
사용자: "RLHF의 안전성 문제를 찾아줘"
  ↓ 에이전트가 search_papers 호출
  ↓ 검색 문서 자동 생성 → 워크스페이스에 등장
에이전트: "12편을 찾았다. 검색 결과 문서를 열어뒀다. 핵심적인 것들을 분석해볼까?"
  ↓ 사용자 승인
  ↓ 에이전트가 analyze_papers 호출
  ↓ 분석 문서들 생성 → 워크스페이스에 추가
```

---

## 상태 관리 단순화

### 현재: 8개 스토어 + 복잡한 hydration

```
sessionStore → searchStore → analysisStore → importanceStore
    → researchGuideStore → topicStore → workflowStore → translationStore
```

### 변경: 단일 인터페이스로 수렴

```
documentStore       — 균일한 인터페이스 (문서 CRUD, 조회, 검색)
workspaceStore      — 열린 문서 패널 관리, 레이아웃
sessionStore        — 세션 메타 관리 (문서 목록은 documentStore에)
```

### Session 구조 변경

```ts
// 현재: 모놀리식 Session
interface Session {
  papers: { byId: Record<string, PaperCore> };
  search: SearchSlice;
  aiAnalysis: AIAnalysisSlice;
  importance: ImportanceSlice;
  researchGuide: ResearchGuideSlice;
  topicSynthesis: TopicSynthesisSlice;
  workflow: WorkflowSlice;
  translation: TranslationSlice;
}

// 변경: 문서 컬렉션
interface Session {
  id: string;
  name: string;
  documents: Document[];   // 세션의 모든 문서
  createdAt: string;
  updatedAt: string;
}
```

8개 슬라이스가 각각 다른 인터페이스를 가졌던 것이, 문서 컬렉션이라는 하나의 인터페이스로 수렴한다. hydration이 단순해진다: 세션 로드 = 문서 배열 로드.

---

## 렌더링 — 단일 렌더러 + 타입별 인터랙션

### 공통 렌더링

모든 문서는 마크다운 본문을 가진다. 렌더러는 하나다.

```tsx
function DocumentRenderer({ document }: { document: Document }) {
  return (
    <div>
      <DocumentHeader document={document} />
      <MarkdownRenderer content={document.content} />
      <TypeInteraction document={document} />
    </div>
  );
}
```

### 타입별 인터랙션

마크다운 본문 외에 타입에 따른 추가 인터랙션만 다르다:

| 타입 | 추가 인터랙션 |
|------|-------------|
| search | 검색바, 논문 클릭 → 분석 문서 생성 트리거 |
| analysis | 원문 링크, 재분석 버튼 |
| synthesis | 섹션별 재생성, 논문 참조 하이라이트 |
| memo | 마크다운 에디터 |
| discussion | 메시지 입력, 에이전트 응답 스트리밍 |
| overview | 클러스터 선택, 논문 목록 펼치기 |

핵심: 새 문서 타입 추가 = TypeInteraction 컴포넌트 하나 추가. 스토어, 영속 경로, hydration 로직 변경 불필요.

---

## 영속 전략

### 현재: localStorage + 슬라이스별 분산

```
session → localStorage (모놀리식 blob)
```

### 변경: 문서 단위 영속

```
documents → localStorage (또는 향후 서버 DB)
  key: `doc:${sessionId}:${documentId}`
```

문서 단위로 저장하면:
- 부분 로드 가능 (열린 문서만 로드)
- 용량 관리 단순 (문서 단위 삭제)
- 서버 DB 전환 시 마이그레이션 단순 (문서 = 행)

### 용량 제한

| 대상 | 제한 | 전략 |
|------|------|------|
| 세션당 문서 | 100개 | 오래된 문서 아카이브 |
| 문서 본문 | 50KB | 마크다운 기준 충분 |
| metadata | 타입별 상한 | 검색: 논문 100개, 분석: 1개 |

---

## API 라우트 통합

### 현재: 도구별 개별 라우트

```
/api/search, /api/analyze, /api/cluster, /api/topic-synthesis,
/api/key-papers, /api/explore-relevance, /api/embed, /api/translate,
/api/workflow-runs, /api/workflow-runs/[runId]
```

### 변경: 문서 CRUD + 도구 실행

```
POST   /api/documents              — 문서 생성 (사용자 직접 or 도구 결과)
GET    /api/documents/:id          — 문서 조회
PATCH  /api/documents/:id          — 문서 갱신
DELETE /api/documents/:id          — 문서 삭제
GET    /api/documents?session=:id  — 세션 문서 목록

POST   /api/tools/:toolName       — 도구 실행 → 문서 생성/갱신 반환
```

도구 실행 API는 내부적으로 외부 서비스(Semantic Scholar, Gemini, OpenAI)를 호출하고, 결과를 문서로 변환하여 반환한다. 클라이언트 입장에서는 어떤 도구를 호출하든 **동일한 인터페이스(Document)가 돌아온다.**

---

## 에이전트 오케스트레이션 변경

### 현재: Phase별 파이프라인 + orchestrator.ts 조율

Phase 전환 시점을 orchestrator가 감지하고, 각 Phase의 파이프라인을 자동 트리거하고, 결과를 각 스토어에 분배한다.

### 변경: 대화 기반 오케스트레이션

Phase 개념이 사라진다. 에이전트가 대화 맥락에서 다음 행동을 판단한다.

```
사용자: "RLHF safety 관련 논문 찾아줘"
에이전트 판단:
  1. search_papers("RLHF safety") → 검색 문서 생성
  2. 결과를 보고 분석 제안 → propose("핵심 논문 5편을 분석해볼까?")
  3. 승인 시 analyze_papers → 분석 문서 5개 생성
  4. 분석 결과를 보고 구조화 제안 → "연구 줄기별로 정리해볼까?"
  5. 승인 시 cluster_papers → 개관 문서 생성
```

현재 코드가 자동 트리거하던 것(Phase 1→2 자동 전환, Phase 3 자동 클러스터링)을 에이전트의 판단으로 옮긴다. 이것이 service-principles.md §맥락 안에서의 자율성의 더 정확한 구현이다.

### 3-Phase Turn Pipeline 유지

현재 구현된 턴 파이프라인(Phase 1: Execute → Phase 2: Post → Phase 3: Dialogue)은 유지한다. 문서 생성이 Phase 2(Post)에서 일어나고, Phase 3(Dialogue)에서 사용자에게 결과를 안내한다.

---

## 개발 방법론: 삼분법 + AGENTS.md 동기화

> 참조: [ai-engineering-methodology.md](../../ai-engineering-methodology.md)

기존 프롬프트 위임 방식(`*-prompt.md` → 코딩 에이전트에 일회성 실행)을 폐기한다. 대신 **원칙과 전략이 코드베이스에 살아있어서, 어떤 에이전트가 와도 읽고 따를 수 있는 구조**로 전환한다.

### 삼분법 — lighthouse 적용

| 관점 | 역할 | 위치 | 형태 |
|------|------|------|------|
| **원칙 (Principles)** | 에이전트가 판단할 때 참조하는 기준. 프롬프트에 주입된다 | `app/principles/*.ts` | 코드 (함수로 export) |
| **전략 (Strategy)** | 코드가 수행하는 구현 방법. 원칙을 참조한다 | `app/strategies/*.ts` | 코드 (구현 로직) |
| **인터페이스 (Interface)** | 입출력 계약. 코드 자체가 명세다 | `app/domain/*.ts` | 타입 정의 |

원래 삼분법의 "출력"을 "인터페이스"로 재해석했다. 균일 인터페이스가 이 재설계의 핵심이므로.

### 구체적 매핑

**원칙 (`app/principles/`)**
```
research-scenarios.ts    — 시나리오별 판단 기준 (새 분야 진입 vs 제안서 준비)
tool-principles.ts       — 도구 사용 원칙 (언제 검색, 언제 분석, 언제 제안)
autonomy-levels.ts       — 자율성 수준별 행동 규칙 (L1~L5)
memory-principles.ts     — 기억 추출/주입 원칙
```

**전략 (`app/strategies/`)**
```
document-creation.ts     — 도구→문서 변환 공통 패턴 (executeTool)
rendering.ts             — 타입별 렌더링 전략
persistence.ts           — 영속 전략 (localStorage, 향후 DB)
orchestration.ts         — 대화→도구→문서 오케스트레이션 흐름
```

**인터페이스 (`app/domain/`)**
```
document.ts              — Document, DocumentType, DocumentMetadata (핵심 계약)
paper.ts                 — PaperCore (기존 유지)
analysis.ts              — AIAnalysis (기존 유지)
workspace.ts             — WorkspaceLayout, PanelState
```

### .md/.ts 이중화 기준

모든 것을 쌍으로 만들지 않는다. 기준:

| 대상 | .md | .ts | 이유 |
|------|:---:|:---:|------|
| 서비스 대원칙 | O | — | 인간이 읽는 철학. 코드 주입 불필요 |
| 아키텍처 결정 | O | — | 설계 근거. 코드가 아닌 문서 |
| 도구/시나리오 원칙 | — | O | 프롬프트에 주입. 코드가 원본 |
| 인터페이스 정의 | — | O | 코드 자체가 명세 |
| 동기화 규칙 | O (AGENTS.md) | — | 에이전트 행동 지침 |

핵심: **원본이 하나**여야 한다. .md가 원본이면 .ts를 만들지 않고, .ts가 원본이면 .md를 만들지 않는다. 이중화는 동기화 실패의 원인이다.

### AGENTS.md — 동기화 규칙

lighthouse 저장소의 `AGENTS.md`가 코딩 에이전트의 행동 규칙을 정의한다:

```markdown
# Light House — AGENTS.md

## 문서 맵
| 문서 | 역할 |
|------|------|
| docs/service-principles.md | 서비스 대원칙 (WHY) |
| docs/document-architecture.md | 균일 인터페이스 설계 (WHAT) |
| docs/conventions.md | 코딩 규칙 (HOW) |

## 인터페이스 규약
모든 도구 출력, 사용자 행동, 저장, 렌더링은 Document 인터페이스를 통과한다.
→ app/domain/document.ts가 계약의 원본이다.

## 동기화 규칙

### 도구 원칙 변경 시
app/principles/tool-principles.ts 수정
  → 시스템 프롬프트(system-prompt.ts) 주입 부분 확인
  → docs/service-principles.md와 방향성 일치 확인

### 문서 타입 추가 시
app/domain/document.ts에 DocumentType 추가
  → app/strategies/document-creation.ts에 생성 패턴 추가
  → app/strategies/rendering.ts에 TypeInteraction 추가
  → 새 스토어, 새 영속 경로 추가 금지 (균일 인터페이스 원칙)

### 도구 추가 시
app/principles/tool-principles.ts에 원칙 추가
  → app/strategies/document-creation.ts에 executeTool 패턴 추가
  → app/domain/document.ts에 metadata 타입 추가
  → API: POST /api/tools/:toolName 패턴 따르기
```

---

## 마이그레이션 경로

### 단계 0: 방법론 기반 세팅

- AGENTS.md 작성 (문서 맵 + 인터페이스 규약 + 동기화 규칙)
- `app/domain/document.ts` — Document 인터페이스 정의 (계약의 원본)
- `app/principles/` — 도구 원칙, 시나리오 원칙, 자율성 규칙
- `app/strategies/` — 문서 생성 패턴, 렌더링 전략, 영속 전략
- 기존 `*-prompt.md` 위임 방식 폐기

### 단계 1: Document 모델 도입

- documentStore 구현 (균일 CRUD 인터페이스)
- 기존 데이터를 Document로 변환하는 어댑터

### 단계 2: 도구 출력 통일

- 각 도구의 출력을 Document로 래핑
- API 라우트는 기존 유지, 클라이언트 측에서 Document로 변환
- 기존 스토어와 공존 (점진적 전환)

### 단계 3: 워크스페이스 UI

- 단일 /workspace/[sessionId] 페이지
- 사이드바 + 다중 패널 레이아웃
- DocumentRenderer 통합 렌더러
- Phase 기반 페이지 제거

### 단계 4: 상태 관리 단순화

- 기존 8개 스토어 → documentStore + workspaceStore + sessionStore
- 기존 슬라이스 제거
- hydration 단순화

### 단계 5: 사용자 행동 개방

- 사용자 검색 (검색 문서 직접 생성)
- 사용자 메모 (메모 문서 생성/편집)
- 문서 편집 (에이전트 생성 문서도 수정 가능)

---

## 보존하는 것

이 재설계에서 바꾸지 않는 것:

- **service-principles.md** — 대원칙, 동료 원칙 4가지, 에이전트 계층 구조
- **자율성 5단계 (L1~L5)** — 도구별 자율성 수준은 유지, Phase별 자율성 매핑만 제거
- **FSM 패턴** — 워크플로우 상태 전이와 게이트는 유지 (Phase가 아닌 도구 실행 단위로 적용)
- **관측 체계** — AI 호출, 도구 실행 추적은 문서 생성 이벤트와 통합
- **기억 시스템** — 경험 기억, 사용자 기억은 그대로 유지
- **3-Phase Turn Pipeline** — 대화 오케스트레이션 구조 유지
- **캐시 우선 복원** — 문서 단위 캐시로 전환하되, 원칙은 동일

---

## 검증 기준

재설계가 성공했다면:

1. **인터페이스 균일성** — 모든 도구 출력, 사용자 행동, 저장, 렌더링이 동일한 인터페이스(문서 CRUD)를 통과한다
2. **확장 비용** — 새 도구 추가 = DocumentType 1개 + metadata 타입 + TypeInteraction 컴포넌트. 인터페이스 변경 없음
3. **대칭성** — 사용자와 에이전트가 동일한 인터페이스로 참여한다
4. **자유도** — 종합 분석 중에 새 검색을 시작할 수 있다. 인터페이스가 같으니 조합이 자유롭다
5. **단순성** — 8개 스토어(각각 다른 인터페이스) → 3개 스토어(하나의 인터페이스)
6. **에이전트 자율성** — 새 코딩 에이전트가 AGENTS.md를 읽고 원칙/전략/인터페이스를 파악하여 일관된 코드를 생성할 수 있다. 별도 프롬프트 위임 불필요
