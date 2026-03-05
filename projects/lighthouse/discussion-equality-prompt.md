# discussion 문서 동등화 — 후속 프롬프트

> 선행: collection 문서 타입 도입 완료 (417d421)

## 목표

"모든 것은 문서다" 철학 완성. 현재 discussion(채팅)이 4곳에서 특수 처리되어 다른 문서와 동등하지 않다. 이를 제거하여 discussion도 search, analysis, memo와 동일한 시민권을 갖게 한다.

## 현재 문제 (4곳)

| 위치 | 특수 처리 | 문제 |
|------|----------|------|
| `Sidebar.tsx:208` | `d.type !== "discussion"` 필터 | 사이드바 문서 목록에서 제외됨 |
| `DocumentStrip.tsx:100` | `doc.type !== "discussion"` → onClose undefined | 닫기 불가 |
| `DocumentStrip.tsx:166-200` | `isConversation` → 타이틀 바 미표시 | 다른 문서와 다른 외형 |
| `TileWorkspace.tsx:60-67` | `doc.type !== "discussion"` → focusedDoc 제외 | 포커스 대상에서 배제 |

## 변경 사항

### 1. Sidebar — discussion을 문서 목록에 표시

**파일**: `app/components/Sidebar.tsx`

```ts
// Before
const nonDiscussionDocs = documents.filter(
  (d) => d.type !== "discussion" && d.type !== "collection"
);

// After — collection만 제외 (collection은 상위 레벨에서 관리되므로)
const visibleDocs = documents.filter((d) => d.type !== "collection");
```

discussion 문서가 사이드바 문서 목록에 💬 아이콘과 함께 다른 문서와 나란히 표시된다.

### 2. DocumentStrip — discussion도 닫기 가능 + 타이틀 바 표시

**파일**: `app/components/workspace/DocumentStrip.tsx`

```ts
// Before (100줄)
onClose={doc.type !== "discussion" ? () => handleCloseDocument(doc.id) : undefined}

// After — 모든 문서 동일하게 닫기 가능
onClose={() => handleCloseDocument(doc.id)}
```

타이틀 바도 동일하게 표시:
```ts
// Before (127줄)
const isConversation = doc.type === "discussion";
// 이 변수를 사용하여 타이틀 바를 숨기는 분기 제거

// After — discussion도 다른 문서와 동일한 타이틀 바 (💬 아이콘 + 제목)
// isConversation 분기를 제거하고 모든 문서에 동일한 타이틀 바 적용
```

### 3. TileWorkspace — discussion도 포커스 대상

**파일**: `app/components/workspace/TileWorkspace.tsx`

```ts
// Before (60-67줄)
const focusedDoc = useMemo(() => {
  for (const id of visibleDocIds) {
    const doc = documents.find((d) => d.id === id);
    if (doc && doc.type !== "discussion") return doc;
  }
  return undefined;
}, [visibleDocIds, documents]);

// After — 타입 무관하게 첫 번째 가시 문서가 포커스
const focusedDoc = useMemo(() => {
  for (const id of visibleDocIds) {
    const doc = documents.find((d) => d.id === id);
    if (doc) return doc;
  }
  return undefined;
}, [visibleDocIds, documents]);
```

### 4. 닫았을 때 동작

discussion을 닫으면 다른 문서와 동일하게 워크스페이스에서 제거된다. 사이드바 문서 목록에는 남아 있으므로 클릭하면 다시 열 수 있다. DB에서 삭제하지는 않는다 (discussion은 세션의 대화 기록이므로).

**파일**: `app/components/workspace/DocumentStrip.tsx` — `handleCloseDocument`

```ts
// discussion 닫기 시: 워크스페이스에서만 제거, DB 삭제는 하지 않음
// 기존 handleCloseDocument가 DELETE API를 호출한다면,
// discussion 타입은 API 호출 없이 스토어에서만 제거
const handleCloseDocument = (docId: string) => {
  const doc = documents.find(d => d.id === docId);
  if (doc?.type === "discussion") {
    // 워크스페이스에서만 제거 (DB 유지)
    removeDocument(docId);
  } else {
    // 기존 동작 (DB에서도 삭제)
    removeDocument(docId);
    // DELETE API 호출...
  }
};
```

## 건드리지 않는 것

- collection 필터링 (`d.type !== "collection"`) — collection은 상위 레벨에서 관리
- discussion 문서의 내부 렌더링 (ConversationDocument 컴포넌트) — 메시지 입력/스트리밍은 그대로
- DB 스키마, API 라우트 — 변경 없음

## 검증

- [ ] 사이드바 문서 목록에 💬 discussion이 다른 문서와 나란히 표시됨
- [ ] discussion 클릭 시 워크스페이스에서 해당 위치로 스크롤
- [ ] discussion 패널에 타이틀 바(💬 + 제목)가 표시됨
- [ ] discussion 닫기(x) 가능 → 워크스페이스에서 제거, 사이드바에는 남음
- [ ] 사이드바에서 discussion 다시 클릭 → 워크스페이스에 복원
- [ ] discussion이 없는 워크스페이스에서도 정상 동작 (채팅 없이 문서만 보는 경우)
- [ ] 기존 세션(마이그레이션 전)에서도 정상 동작
