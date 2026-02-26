# 세션 전환 시 연구 문서 패널 리셋 구현 프롬프트

> 세션을 전환하면 이전 세션의 연구 문서가 패널에 남아있는 버그를 수정한다.

## 원인

`usePanelStore`는 Zustand `create()`로 생성된 글로벌 스토어다.
세션 전환(router.push) 시 Next.js가 페이지를 리마운트하지만, Zustand store는 메모리에 유지된다.
`NotebookCanvas`의 useEffect가 새 세션의 artifacts를 로드할 때, 기존 documents를 비우지 않고 추가만 한다.

결과: 이전 세션의 연구 문서가 패널에 남아있다.

## 수행할 작업

`app/components/NotebookCanvas.tsx`의 패널 hydration useEffect에서, 새 세션의 artifacts를 로드하기 전에 기존 documents를 초기화한다.

```
// 현재: 기존 documents에 추가만 함
for (const doc of searchDocs) {
  store.setDocument(...);
}

// 변경: 먼저 초기화한 후 로드
store.clearDocuments();  // ← 추가
for (const doc of searchDocs) {
  store.setDocument(...);
}
```

`app/stores/panel-store.ts`에 `clearDocuments` 액션을 추가한다.

```
clearDocuments: () => set({ documents: [], activeDocumentId: null }),
```

## 참조 파일

| 파일 | 변경 |
|------|------|
| `app/stores/panel-store.ts` | `clearDocuments` 액션 추가 |
| `app/components/NotebookCanvas.tsx` | 패널 hydration useEffect에서 clearDocuments 호출 추가 |

## 완료 기준

- [ ] 세션 A에서 검색 → 연구 문서 생성 → 세션 B로 전환 → 패널에 세션 A 문서가 보이지 않음
- [ ] 세션 B에서 다시 세션 A로 전환 → 세션 A의 연구 문서가 정상 로드됨
- [ ] 새 세션(문서 없음) 시작 시 패널이 비어있음
