# 공동 도구 사용 — 구현 프롬프트

## 배경

현재 Lighthouse에서 사용자가 할 수 있는 건 텍스트 입력뿐이다. 검색, 분석, 문서 작성은 모두 AI가 수행한다. 이번 작업에서 **사용자도 직접 검색하고, 검색 결과에서 논문을 선택해 AI 분석을 트리거**할 수 있게 한다.

핵심 원칙: **문서가 두 주체(사용자와 AI)의 공유 매체다.** 누가 검색했든 결과는 같은 형태의 문서로 생성되고, AI는 그 문서를 읽어서 사용자 행동을 인지한다.

이번 작업과 함께 **기존 보일러플레이트를 정리하고 깨끗하게 재작성**한다.

---

## 설계 문서

`/Users/jaeyoungkang/mirror-mind/projects/lighthouse/shared-tools-design.md` 참조

---

## 현재 구조 요약

```
app/
├── components/
│   ├── NotebookShell.tsx          # 3컬럼 레이아웃 (사이드바|노트북|패널)
│   ├── NotebookCanvas.tsx         # 메인 채팅 캔버스
│   ├── NotebookInputBar.tsx       # 텍스트 입력만 가능
│   ├── panels/
│   │   └── ResearchDocPanel.tsx   # 우측 패널 — 마크다운 문서 렌더링
│   ├── blocks/                    # 메시지 블록 렌더러
│   └── artifacts/renderers/       # 도구별 결과 렌더러
├── server/
│   ├── agent/
│   │   ├── orchestrator.ts        # 3-Phase Pipeline (Execute→Post→Dialogue)
│   │   ├── system-prompt.ts       # 시스템 프롬프트
│   │   ├── tools.ts               # 도구 세트 구성
│   │   ├── post-actions.ts        # Phase 2 자동 처리
│   │   └── pipeline-rules.ts      # 도구별 후처리 규칙
│   ├── tools/                     # 9개 도구 구현
│   └── repository/                # DB 접근
├── stores/
│   ├── panel-store.ts             # 패널 문서 상태
│   └── agent-store.ts             # 에이전트 FSM
└── domain/                        # 타입 정의
```

---

## 변경 1: 사용자 검색 UI

### 연구 문서 패널에 검색바 추가

`ResearchDocPanel.tsx`의 헤더 영역에 검색 입력 필드를 추가한다.

```
┌─ 연구 문서 패널 ──────────────────┐
│ [검색바: 키워드 입력] [🔍 검색]    │  ← 새로 추가
│ ┌─ 탭: 검색결과1 | 분석문서1 ──┐  │
│ │                              │  │
│ │  (마크다운 문서 렌더링)       │  │
│ │                              │  │
│ └──────────────────────────────┘  │
└───────────────────────────────────┘
```

**검색 실행 흐름:**
1. 사용자가 검색바에 키워드 입력 → 검색 버튼 클릭 (또는 Enter)
2. 프론트엔드에서 직접 `/api/search` 호출 (새 API 엔드포인트)
3. 서버: 기존 `search-papers.ts`의 Semantic Scholar API 호출 로직 재사용
4. 검색 결과를 문서 형태로 생성 → 패널에 표시
5. 검색 결과 문서를 DB에 저장 (artifact로, 기존 search_results 타입)

**새 API 엔드포인트: `/api/search`**

```ts
// app/api/search/route.ts
// POST { query, conversationId, limit?, year? }
// → Semantic Scholar 검색 실행
// → artifact 저장 (paper_collection + search_results)
// → 검색 결과 문서 반환 { documentId, title, content, papers }
```

핵심: 기존 `search-papers.ts`의 검색 로직을 **공통 함수로 추출**하여 AI 도구 호출과 사용자 직접 호출 양쪽에서 재사용한다.

```
기존: search-papers.ts (도구 전용)
변경: lib/search-service.ts (공통 로직)
       ├── search-papers.ts (AI 도구 → 공통 로직 호출)
       └── api/search/route.ts (사용자 직접 → 공통 로직 호출)
```

---

## 변경 2: 논문 클릭 → AI 분석 트리거

### 검색 결과 문서에서 논문 선택

검색 결과 문서의 각 논문 항목을 클릭 가능하게 만든다. 현재 논문 리스트는 ````papers` 코드블록으로 렌더링되고 있다 (PaperListBlock 등).

**클릭 흐름:**
1. 사용자가 검색 결과에서 논문을 클릭
2. 프론트엔드에서 `/api/analyze` 호출 (새 API 엔드포인트)
3. 서버: 기존 `analyze-papers.ts`의 분석 로직 재사용 → 해당 논문 분석
4. 분석 결과를 문서 형태로 생성 → 패널에 새 탭으로 표시

**새 API 엔드포인트: `/api/analyze`**

```ts
// app/api/analyze/route.ts
// POST { papers: [{ paperId, title, abstract }], conversationId }
// → Gemini 분석 실행
// → 분석 결과 문서 반환 { documentId, title, content }
```

마찬가지로 `analyze-papers.ts`의 분석 로직을 공통 함수로 추출한다.

---

## 변경 3: AI가 사용자 행동 인지

### 사용자 행동을 대화 맥락에 포함

사용자가 직접 검색하거나 논문을 선택하면, 그 행동을 AI가 인지해야 한다. 방법: **사용자 행동을 대화 메시지로 기록**한다.

```ts
// 사용자가 검색 실행 시
await appendMessage({
  conversationId,
  type: "user",
  text: "",  // 빈 텍스트
  metadata: {
    action: "user_search",
    query: "transformer attention mechanism",
    resultCount: 20,
    documentId: "search-xxx",
  }
});

// 사용자가 논문 선택 시
await appendMessage({
  conversationId,
  type: "user",
  text: "",
  metadata: {
    action: "user_analyze",
    papers: [{ paperId, title }],
    documentId: "analysis-xxx",
  }
});
```

오케스트레이터는 다음 턴에서 이 메시지들을 보고 맥락을 파악한다. 시스템 프롬프트에 다음 섹션 추가:

```
## 사용자 직접 행동
사용자가 직접 검색하거나 논문을 선택할 수 있다.
action: "user_search" → 사용자가 직접 검색한 것. 결과 문서가 패널에 있다.
action: "user_analyze" → 사용자가 논문을 선택해서 분석을 요청한 것.
이런 행동이 보이면 사용자의 관심사와 의도를 파악하여 다음 대화에 반영하라.
```

---

## 변경 4: 코드 정리

### 검색 로직 공통화

```
현재:
  server/tools/search-papers.ts     — 검색 + artifact 저장 + 문서 생성 (혼재)
  server/tools/analyze-papers.ts    — 분석 로직 (도구 전용)

변경:
  server/services/search-service.ts — Semantic Scholar 검색 + artifact 저장
  server/services/analyze-service.ts — 논문 분석 (Gemini 호출)
  server/tools/search-papers.ts     — AI 도구 래퍼 (service 호출)
  server/tools/analyze-papers.ts    — AI 도구 래퍼 (service 호출)
  api/search/route.ts               — 사용자 직접 검색 (service 호출)
  api/analyze/route.ts              — 사용자 직접 분석 (service 호출)
```

### 미사용 코드 제거

- `researcher_profile` 아티팩트 타입 — 생성 도구 없음, 제거
- `research_note` 아티팩트 타입 — 수동 작성 불가, 제거
- 사용률 낮은 렌더러 확인 후 정리

### 렌더러 정리

현재 `artifacts/renderers/`에 도구별 렌더러가 분산되어 있다. 사용자 직접 검색 결과도 동일한 렌더러를 쓰므로 **렌더러는 "누가 호출했는지"와 무관**하게 동작해야 한다.

---

## 변경 5: 레이아웃 개편

### 연구 문서 패널 역할 확장

현재 패널은 "AI가 작성한 문서를 읽는 곳"이다. 변경 후에는 **"사용자와 AI가 함께 사용하는 연구 작업 공간"**이 된다.

```
현재:
  패널 = 읽기 전용 문서 뷰어

변경:
  패널 = 연구 작업 공간
  ├── 검색바 (사용자 직접 검색)
  ├── 문서 탭 (검색 결과, 분석 문서)
  └── 논문 클릭 → 분석 트리거
```

### 논문 항목 인터랙션

현재 ````papers` 코드블록의 PaperListBlock은 논문을 표시만 한다. 각 논문 항목에:
- 클릭 → 분석 요청 (위 변경 2)
- 논문 제목, 저자, 연도, 인용수, 초록 미리보기 표시
- 분석 완료된 논문은 시각적 구분 (체크 표시 등)

---

## 구현 순서

1. **서비스 레이어 추출** — search-service.ts, analyze-service.ts로 공통 로직 분리
2. **새 API 엔드포인트** — `/api/search`, `/api/analyze`
3. **패널 검색 UI** — ResearchDocPanel에 검색바 추가
4. **논문 클릭 핸들러** — PaperListBlock 또는 패널 내 논문 항목에 클릭 → 분석 트리거
5. **사용자 행동 기록** — 검색/선택 행동을 대화 메시지로 저장
6. **시스템 프롬프트 업데이트** — 사용자 직접 행동 인지 섹션 추가
7. **코드 정리** — 미사용 타입/렌더러 제거, 보일러플레이트 정리

---

## 주의사항

- 기존 AI 도구 호출 흐름(3-Phase Pipeline)은 **그대로 유지**한다. 사용자 직접 호출은 별도 경로로 추가
- 검색 결과 문서 형태는 기존과 **동일**하게 유지 — 문서가 공유 매체이므로 형태가 달라지면 안 된다
- `panel-store.ts`의 `setDocument()`를 그대로 활용 — 사용자 검색 결과도 같은 방식으로 패널에 추가
- 인증/권한은 이 단계에서 고려하지 않는다

---

## 참조 문서

- 설계 원본 (mirror-mind): `/Users/jaeyoungkang/mirror-mind/projects/lighthouse/shared-tools-design.md`
- 서비스 원칙 (lighthouse): `docs/service-principles.md`
- 연구 시나리오 (mirror-mind): `/Users/jaeyoungkang/mirror-mind/projects/lighthouse/research-scenarios.md`
