# 타일 워크스페이스 구현 프롬프트

> 설계 근거: `shared-tools-design.md`
> 서비스 원칙: `service-principles.md`

---

## 목표

현재 3컬럼 고정 레이아웃(Sidebar | Notebook | ResearchDocPanel)을 **타일 워크스페이스**로 완전 교체한다. "Everything is a document" — 대화, 검색 결과, 분석, 메모가 모두 동등한 문서이며, 사용자가 타일에 자유롭게 배치한다.

핵심 변경:
1. 대화 영역 vs 문서 패널 분리가 사라진다
2. 사용자도 문서를 만든다 (메모)
3. 하단 글로벌 대화 입력으로 어디서든 corca와 소통
4. 여러 문서를 나란히 펼쳐볼 수 있다 (타일 분할)

---

## 변경 범위

### 살리는 것 (수정 없이 재사용)
- `server/agent/orchestrator.ts` — 3-Phase 파이프라인 (Phase 2.5 post-action 출력만 변경)
- `server/agent/system-prompt.ts` — 시스템 프롬프트
- `server/agent/tools.ts` — 도구 등록
- `server/agent/pipeline-rules.ts` — 파이프라인 규칙
- `server/tools/*.ts` — 8개 도구 함수 전부
- `server/services/*.ts` — 비즈니스 로직 전부
- `server/memory/` — v3 기억 시스템 전부
- `server/repository/` — 데이터 접근
- `lib/observe.ts` — TurnContext 관측
- `lib/llm-judgment.ts` — LLM 판단 유틸
- `lib/messages-to-blocks.ts` — 메시지→블록 변환
- `domain/` — 타입 정의 (확장만)
- `api/` — API 라우트 (수정 최소)
- DB 스키마 — 기존 테이블 유지, 확장만

### 교체하는 것
- `components/NotebookShell.tsx` → `components/workspace/TileWorkspace.tsx`
- `components/NotebookCanvas.tsx` → `components/documents/ConversationDocument.tsx` + `components/workspace/GlobalChatInput.tsx`
- `components/panels/ResearchDocPanel.tsx` → 타일 시스템에 흡수 (삭제)
- `stores/panel-store.ts` → `stores/workspace-store.ts`

### 새로 만드는 것
- `stores/workspace-store.ts` — 타일 레이아웃 + 탭 + 문서 레지스트리
- `components/workspace/TileWorkspace.tsx` — 최상위 워크스페이스
- `components/workspace/TileContainer.tsx` — 분할 컨테이너
- `components/workspace/Tile.tsx` — 개별 타일 (탭바 포함)
- `components/workspace/TabBar.tsx` — 탭 관리
- `components/workspace/TileResizer.tsx` — 드래그 크기 조절
- `components/workspace/GlobalChatInput.tsx` — 하단 글로벌 입력
- `components/documents/ConversationDocument.tsx` — 대화 문서
- `components/documents/SearchDocument.tsx` — 검색 결과 문서
- `components/documents/AnalysisDocument.tsx` — 분석 문서
- `components/documents/MemoDocument.tsx` — 사용자 메모 문서
- `components/documents/DocumentShell.tsx` — 문서 공통 래퍼

---

## Phase 1: 워크스페이스 프레임워크

### 1-1. workspace-store.ts

panel-store.ts를 교체한다.

```typescript
// === 타입 정의 ===

type DocumentType = "conversation" | "search" | "analysis" | "memo";

interface WorkspaceDocument {
  id: string;
  type: DocumentType;
  title: string;
  content: string;          // 마크다운 (검색, 분석) 또는 빈 문자열 (대화)
  createdAt: number;
  updatedAt: number;
  conversationId: string;   // 소속 대화
  editable: boolean;        // 사용자 편집 가능 여부
}

// 타일 트리 구조: 분할 컨테이너 또는 리프 타일
type TileNode =
  | { type: "split"; direction: "horizontal"; children: [TileNode, TileNode]; ratio: number }
  | { type: "leaf"; tileId: string };

interface TileState {
  tabIds: string[];         // 문서 ID 목록
  activeTabId: string;      // 현재 활성 탭
}

interface WorkspaceState {
  // 문서 레지스트리
  documents: Map<string, WorkspaceDocument>;

  // 타일 트리
  tileTree: TileNode;
  tiles: Map<string, TileState>;  // tileId → 탭 상태
  focusedTileId: string;

  // 사이드바
  sidebarCollapsed: boolean;

  // 액션
  openDocument(doc: WorkspaceDocument, targetTile?: "same" | "opposite"): void;
  closeTab(tileId: string, docId: string): void;
  setActiveTab(tileId: string, docId: string): void;
  moveTab(fromTileId: string, toTileId: string, docId: string): void;
  setFocusedTile(tileId: string): void;
  setSplitRatio(ratio: number): void;
  updateDocument(docId: string, updates: Partial<WorkspaceDocument>): void;
  toggleSidebar(): void;
}
```

**openDocument 동작 규칙:**
- 단일 타일 상태에서 호출 시: 자동 2분할, 새 문서를 오른쪽 타일에
- 2분할 상태에서 `targetTile="opposite"`: 포커스 반대쪽 타일에 탭 추가
- 2분할 상태에서 `targetTile="same"`: 현재 포커스 타일에 탭 추가
- 기본값: `"opposite"`
- 이미 열려 있는 문서 ID면: 해당 탭으로 포커스 이동 (중복 안 열림)

**closeTab 동작 규칙:**
- 마지막 탭이 닫히면 해당 타일 제거, 단일 타일로 복귀
- 대화 문서는 닫기 불가 (최소 하나는 존재)

### 1-2. TileWorkspace.tsx

NotebookShell.tsx를 교체하는 최상위 컴포넌트.

```
┌────────┬─────────────────────────────────────────┐
│Sidebar │  TileContainer                          │
│        │  (tileTree 기반 재귀 렌더링)              │
│        │                                         │
│        │                                         │
│        │                                         │
│        ├─────────────────────────────────────────┤
│        │  GlobalChatInput                        │
└────────┴─────────────────────────────────────────┘
```

- Sidebar는 기존 Sidebar.tsx 재사용 (대화 목록)
- TileContainer는 tileTree를 재귀 렌더링
- GlobalChatInput은 하단 고정

### 1-3. TileContainer.tsx

tileTree를 재귀적으로 렌더링한다.

- `type: "split"` → 두 자식을 ratio에 따라 분할. 사이에 TileResizer
- `type: "leaf"` → Tile 컴포넌트 렌더링

### 1-4. Tile.tsx

개별 타일. 상단에 TabBar, 본문에 활성 문서 렌더링.

```
┌─ [대화] [검색1] ─────── [+] ─┐
├──────────────────────────────┤
│                              │
│  활성 문서 컴포넌트 렌더링     │
│  (DocumentShell)             │
│                              │
└──────────────────────────────┘
```

- TabBar에서 탭 클릭 → setActiveTab
- `+` 버튼 → 새 메모 문서 생성
- 문서 타입에 따라 적절한 Document 컴포넌트 렌더링

### 1-5. TabBar.tsx

- 탭 목록 렌더링 (문서 제목 + 닫기 버튼)
- 탭 드래그로 순서 변경 / 다른 타일로 이동
- `+` 버튼으로 새 메모 생성
- 활성 탭 하이라이트

### 1-6. TileResizer.tsx

- 타일 사이 경계에 위치
- 마우스 드래그로 ratio 조절
- 최소 비율 제한 (20% 이하로 줄이지 못함)

### 1-7. layout 교체

`app/(chat)/layout.tsx`에서 NotebookShell → TileWorkspace로 교체.

---

## Phase 2: 대화 문서 + 글로벌 입력

### 2-1. ConversationDocument.tsx

기존 NotebookCanvas.tsx에서 **대화 렌더링 부분만** 추출한다.

포함하는 것:
- 메시지 블록 렌더링 (BlockRenderer 재사용)
- 스크롤 관리 (새 메시지 시 자동 스크롤)
- ThinkingHUD (corca 작업 중 표시)
- 제안 카드 (ProposalBlock)

포함하지 않는 것:
- 입력 필드 (GlobalChatInput로 분리)
- useChat 훅 (상위로 끌어올림)

### 2-2. GlobalChatInput.tsx

하단 고정 입력 바.

```
┌──────────────────────────────────────────────────┐
│ [💬 코르카에게...                          ] [전송] │
└──────────────────────────────────────────────────┘
```

- 텍스트 입력 + 전송 버튼
- Enter로 전송, Shift+Enter로 줄바꿈
- 전송 시 현재 포커스된 타일의 활성 문서 ID를 메시지와 함께 전달
  - 이 맥락 정보는 서버로 전달되어, corca가 사용자의 현재 컨텍스트를 안다
- corca 작업 중일 때 중단 버튼 표시

### 2-3. useChat 훅 위치

**TileWorkspace 레벨**에서 useChat을 호출한다. ConversationDocument와 GlobalChatInput이 같은 chat 상태를 공유해야 하기 때문.

```
TileWorkspace
├─ useChat() → messages, append, isLoading, stop
├─ TileContainer
│   └─ Tile
│       └─ ConversationDocument ← messages, isLoading 전달
└─ GlobalChatInput ← append, stop 전달
```

### 2-4. 맥락 전달 (서버 연동)

메시지 전송 시 추가 메타데이터:
```typescript
append({
  role: "user",
  content: userText,
  // 추가:
  experimental_attachments: [{
    name: "workspace-context",
    contentType: "application/json",
    content: JSON.stringify({
      focusedDocumentId: focusedDoc.id,
      focusedDocumentType: focusedDoc.type,
      focusedDocumentTitle: focusedDoc.title,
    }),
  }],
});
```

서버 orchestrator.ts에서 이 메타데이터를 읽어 시스템 프롬프트에 주입:
```
현재 사용자가 보고 있는 문서: {title} ({type})
```

이렇게 하면 "이거 분석해줘"에서 "이거"가 무엇인지 corca가 안다.

---

## Phase 3: corca 문서 (검색, 분석)

### 3-1. SearchDocument.tsx

검색 결과를 표시하는 읽기 전용 문서.

- 상단: 검색 쿼리 표시
- 본문: 논문 목록 (기존 PaperListBlock 재활용)
- 각 논문 항목: 제목, 저자, 년도, 인용수, 한줄 요약
- 논문 클릭 → corca에게 분석 요청 트리거 (글로벌 입력으로 자동 전송 or 제안)
- 드래그 시작점: 논문 항목을 메모 문서로 드래그 가능

현재 `searchResultsDoc` (마크다운 문자열)을 그대로 렌더링하되, 논문 항목은 구조화된 데이터로 관리하여 인터랙션 지원.

### 3-2. AnalysisDocument.tsx

corca가 작성하는 분석 문서. 마크다운 렌더링.

- 갭 분석, 트리아지, 클러스터링, 종합 분석 등
- 기존 ResearchDocPanel이 하던 것과 동일하지만, 이제 타일 안의 하나의 문서
- 읽기 전용

### 3-3. post-actions.ts 수정

기존: `setDocument()` → panel-store에 문서 추가 + 패널 펼침
변경: workspace-store의 `openDocument()`를 호출

```typescript
// 기존
usePanelStore.getState().setDocument(id, title, content, docType);

// 변경
useWorkspaceStore.getState().openDocument({
  id,
  type: docType === "search_results" ? "search" : "analysis",
  title,
  content,
  conversationId,
  editable: false,
}, "opposite");  // 현재 포커스 반대쪽에 열기
```

서버→클라이언트 전달 방식: 기존과 동일하게 SSE 스트림의 data 이벤트로 문서 생성 정보를 전달. 클라이언트에서 수신 시 openDocument 호출.

### 3-4. 아티팩트 렌더러 정리

기존 `artifacts/renderers/` 중:
- `SearchPapersResult.tsx` → SearchDocument가 대체
- `UpdateResearchPanelResult.tsx` → 삭제 (패널 없음)
- 나머지 렌더러 → ConversationDocument 안에서 인라인으로 계속 사용

---

## Phase 4: 사용자 문서 (메모)

### 4-1. MemoDocument.tsx

사용자가 직접 작성하는 마크다운 문서.

- **인라인 편집**: 클릭하면 바로 편집 모드 (노션 스타일)
- **제목 편집**: 상단 제목 클릭으로 변경
- **서식**: 제목(#, ##), 볼드(**), 리스트(-, 1.), 링크
- **자동 저장**: 입력 후 debounce (500ms) → workspace-store 업데이트
- **논문 참조 삽입**: 드롭 대상 — SearchDocument에서 논문 항목을 드래그하면 참조 블록 삽입

### 4-2. 논문 드래그&드롭

SearchDocument 논문 항목 → MemoDocument로 드래그:

1. SearchDocument에서 논문 항목에 `draggable` 설정
2. 드래그 시 논문 메타데이터(paperId, title, authors, year) 전달
3. MemoDocument에서 `onDrop` 수신
4. 드롭 위치에 논문 참조 마크다운 삽입:
   ```markdown
   > **Attention Is All You Need** (Vaswani et al., 2017)
   > [Semantic Scholar](https://semanticscholar.org/paper/...)
   ```

### 4-3. 메모 생성 흐름

- TabBar의 `+` 버튼 클릭
- workspace-store에 새 MemoDocument 등록
  ```typescript
  openDocument({
    id: generateId(),
    type: "memo",
    title: `메모 ${formatDate(now)}`,
    content: "",
    conversationId: currentConversationId,
    editable: true,
  }, "same");  // 현재 타일에 탭 추가
  ```
- 새 탭이 활성화되고 바로 편집 시작

### 4-4. 메모 영속화

현재는 클라이언트 상태만으로 시작. 서버 저장은 후속 작업:
- 일단 workspace-store (Zustand)에만 보관
- 페이지 새로고침 시 메모 소실 (MVP에서는 허용)
- 후속: artifacts 테이블에 type="memo"로 저장

---

## Phase 5: 안정화 + 마이그레이션

### 5-1. 기존 기능 호환성

- 대화 생성/로드 → ConversationDocument에서 정상 동작
- 검색 → SearchDocument로 결과 표시
- 분석 → AnalysisDocument 또는 ConversationDocument 인라인
- 제안 카드 → ConversationDocument에서 기존 ProposalBlock 동작
- 기억 시스템 → 변경 없음 (orchestrator 그대로)
- 온보딩 → ConversationDocument에서 기존 흐름 유지

### 5-2. 삭제 대상

Phase 1~4 완료 후 삭제:
- `components/NotebookShell.tsx`
- `components/NotebookCanvas.tsx`
- `components/panels/ResearchDocPanel.tsx`
- `stores/panel-store.ts`
- `components/artifacts/renderers/UpdateResearchPanelResult.tsx`

### 5-3. 확인 체크리스트

- [ ] 앱 진입 시 단일 타일 + 대화 문서
- [ ] 검색 실행 시 자동 2분할 + 검색 문서 표시
- [ ] 탭 클릭으로 문서 전환
- [ ] 탭 닫기 → 마지막 탭이면 타일 제거
- [ ] 글로벌 입력으로 어떤 문서를 보면서든 corca와 대화
- [ ] 맥락 전달 — 검색 문서를 보면서 "이 중 핵심은?" → corca가 검색 결과 맥락 파악
- [ ] + 버튼으로 메모 생성 + 인라인 편집
- [ ] 논문 드래그&드롭 (검색→메모)
- [ ] 타일 크기 조절 (드래그)
- [ ] 제안 카드 정상 동작
- [ ] 기억 활성화 정상 동작
- [ ] 온보딩 흐름 정상 동작

---

## 구현 순서 요약

| Phase | 핵심 산출물 | 의존성 |
|-------|-----------|--------|
| 1 | workspace-store, TileWorkspace, Tile, TabBar | 없음 |
| 2 | ConversationDocument, GlobalChatInput | Phase 1 |
| 3 | SearchDocument, AnalysisDocument, post-actions 수정 | Phase 1, 2 |
| 4 | MemoDocument, 드래그&드롭 | Phase 1, 3 |
| 5 | 레거시 삭제, 호환성 검증 | Phase 1~4 |

**Phase 1 완료 시점에 중간 검증**: 대화 문서 하나로 기존과 동일하게 동작하는지 확인.
**Phase 3 완료 시점에 중간 검증**: 검색→문서 생성→2분할이 자연스럽게 동작하는지 확인.

---

## 설계 판단 기록

| 판단 | 결정 | 이유 |
|------|------|------|
| 타일 트리 구조 | 이진 트리 (split/leaf) | 2분할 기본, 3분할도 자연스럽게 지원 |
| 새 문서 열림 위치 | 포커스 반대쪽 | 시나리오에서 "보면서 비교"가 핵심 패턴 |
| corca 문서 편집 | 읽기 전용 | 공동 편집 복잡도 회피, 초기 단순화 |
| useChat 위치 | TileWorkspace 레벨 | ConversationDocument와 GlobalChatInput이 상태 공유 |
| 메모 영속화 | 클라이언트만 (MVP) | 서버 저장은 후속 |
| 마크다운 에디터 | 직접 구현 (최소) | 외부 라이브러리 의존 최소화, 서식 4종만 |
