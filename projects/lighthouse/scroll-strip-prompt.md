# 스크롤 스트립 전환 — 추가 구현 프롬프트

> 설계 근거: `shared-tools-design.md` §스크롤 스트립 상세 설계
> 이전 구현: `tile-workspace-prompt.md` (Phase 1~5, 타일+탭 방식 — 완료됨)

---

## 목표

현재 구현된 타일+탭 워크스페이스를 **스크롤 스트립**으로 전환한다. 탭을 제거하고, 문서가 옆으로 나열되어 가로 스냅 스크롤로 탐색하는 방식이다.

**핵심 변경:**
- 탭 시스템 제거 — 각 문서가 독립된 패널
- 타일 분할(이진 트리) 제거 — 선형 리스트
- 가로 스크롤 + 1개 단위 스냅 — 화면에 항상 2개 나란히
- 문서 생성 시 리스트에 추가 + 해당 위치로 스크롤

---

## 전환 전후 비교

| | 현재 (타일+탭) | 전환 후 (스크롤 스트립) |
|---|---|---|
| 구조 | TileNode 이진 트리 | `WorkspaceDocument[]` 선형 배열 |
| 문서 전환 | 탭 클릭 | 가로 스크롤 (스냅) |
| 동시 표시 | 2분할 각 타일에 1개씩 | 화면 50%씩 2개 |
| 문서 가시성 | 탭 뒤에 숨겨짐 | 항상 존재, 스크롤로 접근 |
| 크기 조절 | TileResizer 드래그 | 없음 (고정 50%) |

---

## workspace-store 변경

기존 TileNode 트리 구조 → 단순 배열로 교체.

```typescript
interface WorkspaceState {
  // 문서 리스트 (순서 있는 배열)
  documents: WorkspaceDocument[];

  // 사이드바
  sidebarCollapsed: boolean;

  // 액션
  addDocument(doc: WorkspaceDocument, position?: "end" | "after-visible"): void;
  removeDocument(docId: string): void;
  updateDocument(docId: string, updates: Partial<WorkspaceDocument>): void;
  toggleSidebar(): void;
}
```

**삭제할 것:**
- `TileNode` 타입 (split/leaf 트리)
- `TileState` (탭 관리)
- `tiles: Map<string, TileState>`
- `focusedTileId`
- `openDocument()` (복잡한 타일 배치 로직)
- `closeTab()`, `setActiveTab()`, `moveTab()`
- `setFocusedTile()`, `setSplitRatio()`

**addDocument 동작:**
- `position="end"` (기본): 리스트 끝에 추가
- `position="after-visible"`: 현재 화면에 보이는 오른쪽 문서 다음에 삽입
- 추가 후 해당 문서가 보이도록 스크롤 트리거 (scrollIntoView)
- 이미 같은 ID가 있으면 추가하지 않고 해당 문서로 스크롤

**removeDocument 동작:**
- 대화 문서(첫 번째)는 제거 불가
- 제거 시 오른쪽 문서들이 왼쪽으로 당겨짐

---

## 컴포넌트 변경

### 삭제

- `TileContainer.tsx` (재귀 트리 렌더러)
- `Tile.tsx` (개별 타일 + 탭바)
- `TabBar.tsx` (탭 관리)
- `TileResizer.tsx` (드래그 크기 조절)

### 신규: DocumentStrip.tsx

TileContainer를 대체하는 핵심 컴포넌트.

```tsx
// 가로 스크롤 컨테이너
<div
  className="flex overflow-x-auto snap-x snap-mandatory"
  ref={scrollContainerRef}
>
  {documents.map((doc) => (
    <div
      key={doc.id}
      className="snap-start shrink-0"
      style={{ width: documents.length === 1 ? "100%" : "50%" }}
    >
      <DocumentShell document={doc} onClose={() => removeDocument(doc.id)} />
    </div>
  ))}
</div>
```

**CSS scroll-snap 핵심:**
- `scroll-snap-type: x mandatory` — 스크롤 시 반드시 스냅
- `scroll-snap-align: start` — 각 문서가 왼쪽 가장자리에 정렬
- `scroll-behavior: smooth` — 프로그래밍 스크롤 시 부드럽게

**문서 1개일 때:** 너비 100% (전체 사용). 2개 이상이면 50%.

### 수정: TileWorkspace.tsx → ScrollWorkspace.tsx (또는 이름 유지)

```
┌────────┬─────────────────────────────────────────┐
│Sidebar │  DocumentStrip                          │
│        │  (가로 스크롤 스트립)                     │
│        │                                         │
│        │  ┌──────────┬──────────┐                │
│        │  │  문서 A  │  문서 B  │ ← 스냅된 2개   │
│        │  └──────────┴──────────┘                │
│        │                                         │
│        ├─────────────────────────────────────────┤
│        │  GlobalChatInput                        │
└────────┴─────────────────────────────────────────┘
```

### 수정: DocumentShell.tsx

각 문서 패널의 공통 래퍼. 기존과 동일하되:
- **상단 바**: 문서 제목 + X 닫기 버튼 (대화 문서는 X 없음)
- 탭바 제거

### 수정: + 버튼 위치

TabBar가 사라지므로 + 버튼의 새 위치가 필요하다.

옵션: 글로벌 입력 바 옆에 `[+]` 버튼을 둔다.

```
┌──────────────────────────────────────────────────┐
│ [+] [💬 코르카에게...                     ] [전송] │
└──────────────────────────────────────────────────┘
```

또는 스트립 끝(마지막 문서 오른쪽)에 빈 `+` 패널을 둔다. → 스크롤해서 끝까지 가면 + 버튼이 보임.

**추천: 글로벌 입력 바 옆.** 항상 접근 가능하고, 별도 스크롤 불필요.

---

## post-actions.ts 변경

기존 `openDocument()` 호출 → `addDocument()` 호출로 변경.

```typescript
// 기존
useWorkspaceStore.getState().openDocument({...}, "opposite");

// 변경
useWorkspaceStore.getState().addDocument({
  id,
  type: docType === "search_results" ? "search" : "analysis",
  title,
  content,
  conversationId,
  editable: false,
}, "end");  // 리스트 끝에 추가
```

스크롤은 addDocument 내부 또는 컴포넌트 effect에서 처리.

---

## 스크롤 + 맥락 전달

기존 focusedTileId 대신, **현재 화면에 보이는 문서**를 감지한다.

```typescript
// IntersectionObserver로 현재 보이는 문서 감지
const visibleDocIds = useVisibleDocuments(scrollContainerRef);

// 메시지 전송 시 보이는 문서 정보를 맥락으로 전달
append({
  role: "user",
  content: userText,
  experimental_attachments: [{
    name: "workspace-context",
    contentType: "application/json",
    content: JSON.stringify({
      visibleDocuments: visibleDocIds.map(id => ({
        id: doc.id,
        type: doc.type,
        title: doc.title,
      })),
    }),
  }],
});
```

**변경점:** focusedDocument 1개 → visibleDocuments 2개. corca가 사용자가 어떤 두 문서를 나란히 보고 있는지 안다.

---

## 확인 체크리스트

- [ ] 앱 진입 시 대화 문서 1개 (전체 너비)
- [ ] 검색 실행 시 검색 문서 추가 → 자동 스크롤 → [대화][검색] 나란히
- [ ] 분석 실행 시 분석 문서 추가 → 자동 스크롤 → [검색][분석] 나란히
- [ ] 가로 스크롤 시 1개 단위 스냅 (항상 2개가 정렬)
- [ ] 문서 X 클릭 → 리스트에서 제거, 나머지 당겨짐
- [ ] 대화 문서 X 버튼 없음 (닫기 불가)
- [ ] 글로벌 입력에서 보이는 2개 문서 맥락 전달
- [ ] + 버튼으로 메모 생성
- [ ] 기존 기능 정상: 제안 카드, 기억 활성화, 온보딩
