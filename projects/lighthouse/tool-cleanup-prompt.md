# 도구 정리 — 핵심 3개만 남기기

## 목표

현재 8개 도구 중 핵심 경험과 시나리오에 필요한 3개만 남기고 5개를 제거한다. 기존 호환성 유지 불필요. 바닥부터 정리해도 된다.

**남기는 것:**
- `search_papers` — 논문 검색
- `analyze_papers` — 논문 분석
- `propose` — 행동 제안

**제거하는 것:**
- `evaluate_importance` — 핵심 논문 선정
- `cluster_papers` — 주제 분류
- `synthesize_topic` — 종합 리포트
- `translate_abstract` — 초록 번역
- `find_related_papers` — Snowballing

## 변경 파일

### 1. 도구 파일 삭제

다음 파일을 삭제한다:

```
app/server/tools/evaluate-importance.ts
app/server/tools/cluster-papers.ts
app/server/tools/synthesize-topic.ts
app/server/tools/translate-abstract.ts
app/server/tools/find-related-papers.ts
```

### 2. `app/server/tools/index.ts` — export 정리

제거한 도구의 export를 삭제한다. 남는 것:

```ts
export { createSearchPapersTool } from "./search-papers";
export { createAnalyzePapersTool } from "./analyze-papers";
export { createProposeTool } from "./propose";
```

### 3. `app/server/agent/tools.ts` — 도구 등록 정리

```ts
import {
  createSearchPapersTool,
  createAnalyzePapersTool,
  createProposeTool,
} from "@/app/server/tools";

export function createMainTools(conversationId: string, turn?: TurnContext) {
  const raw = {
    search_papers: createSearchPapersTool(conversationId),
    analyze_papers: createAnalyzePapersTool(conversationId),
    propose: createProposeTool(),
  };

  if (!turn) return raw;
  return wrapToolsWithObservation(raw as unknown as ToolMap, turn) as typeof raw;
}
```

`createDialogueTools`는 그대로 유지 (propose만 제공).

### 4. `app/strategies/document-creation.ts` — TOOL_DOCUMENT_TYPE_MAP 정리

```ts
export const TOOL_DOCUMENT_TYPE_MAP: Record<string, DocumentType> = {
  search_papers: "search",
  analyze_papers: "analysis",
};
```

`ARTIFACT_TO_DOCUMENT_MAP`도 현재 사용되는지 확인하고, 사용처가 없으면 삭제한다.

### 5. `app/principles/tool-principles.ts` — 도구 규칙 정리

#### `getToolAutonomyRules()` — 3개 도구만 남긴다

```ts
export function getToolAutonomyRules(): string {
  return `\
## 도구별 자율성 규칙

### search_papers (L3 — 실행 전 제안)
- 기본: propose로 먼저 제안, 승인 후 실행
- 예외: "찾아줘", "검색해줘", "논문 있나?" 같은 직접적 검색 동사 사용 시 propose 없이 실행
- 주제 언급, 질문, 방향 논의는 명시적 요청이 아니다. 반드시 propose 먼저

### analyze_papers (L3 — 실행 전 제안)
- 기본: propose로 먼저 제안, 승인 후 실행
- 예외: "분석해줘", "분석해봐" 같은 명시적 요청 시 propose 없이 실행

### propose (메타 도구)
- L3 도구 실행 전 사용자 확인을 위해 호출
- 사용자가 수락하면 제안한 도구를 즉시 실행. 같은 도구에 대해 propose를 다시 호출하지 않는다`;
}
```

#### `getProposeRules()` — L4, L5 관련 내용 제거, L3만 남긴다

```ts
export function getProposeRules(): string {
  return `\
## propose 도구 사용법

propose는 사용자에게 다음 행동을 구조적으로 제안하는 도구다.
반드시 function calling으로 호출한다. JSON 텍스트로 출력하지 않는다.

### 사용 규칙
1. 도구 실행 전 propose를 호출하여 "이렇게 해볼까?" 제안한다.
2. 사용자가 승인하면 도구를 실행한다.
3. 사용자가 거부하거나 대안을 제시하면 그에 맞춰 수정한다.
4. 버튼 라벨은 맥락에 맞게 구체적으로 쓴다.

### 사용자 응답 처리
- 수락("진행", "좋아", "해줘"): 제안한 행동을 실행
- 대안("다른 방법으로"): 수정된 행동을 실행
- 거부("지금은 안 할래"): 제안을 철회하고 사용자 입력 대기

핵심: 사용자가 수락하면 즉시 실행. 같은 도구에 대해 propose를 다시 호출하지 않는다.`;
}
```

#### `getSearchQueryRules()` — `find_related_papers` 관련 내용 제거

검색 결과 부족 시 "인용망 탐색" 제안 부분을 삭제. 대신:

```
### 검색 결과가 부족할 때
결과가 1~2편이면 같은 의도의 쿼리를 변형하여 재시도하지 않는다. 대신:
- 결과를 사용자에게 보여주고, 키워드를 넓히거나 다른 각도로 검색할지 제안한다.
```

#### `getToolCallRules()` — snowballing, 클러스터링 관련 내용 제거

```
## 도구 호출 규칙

### 한 턴에 하나의 도구
시스템이 한 턴에 하나의 도구만 실행하도록 강제한다.
- 도구를 호출하기 전에 반드시 텍스트를 먼저 생성한다.
- propose 호출 전에도 현재 상황 요약 + 다음 제안 맥락을 텍스트로 생성한다.

### 도구 실행 후 자동 처리
- search_papers 실행 후: 시스템이 자동으로 검색 결과 문서를 생성한다.
- 도구 실행 후 시스템이 대화 이어가기를 요청한다. 결과를 요약하고 인사이트를 공유하라.
```

#### `getDialogueRules()` — 선정/클러스터링 후 대화 규칙 제거

도구 실행 후 대화 연결에서 남기는 것:

```
**검색 후**: 결과 요약 + 다음 단계 제안
**분석 후**: 분석에서 발견한 인사이트를 짚고, 사용자 의견을 묻는다
```

"선정 후", "클러스터링 후" 블록은 삭제.

### 6. `app/domain/document.ts` — DocumentType 정리

현재 사용되는 타입만 남긴다:

```ts
type DocumentType =
  | "search"       // 검색 결과
  | "analysis"     // 논문 분석
  | "memo"         // 사용자 메모
  | "discussion"   // 대화
  | "collection";  // 세션 (폴더)
```

제거:
- `"synthesis"` — synthesize_topic이 없으므로
- `"overview"` — cluster_papers가 없으므로

**주의:** 기존 DB에 synthesis/overview 타입 문서가 있을 수 있다. 마이그레이션에서 기존 데이터를 삭제하거나, 타입 정의는 남기되 도구에서 생성하지 않도록 한다. **기존 데이터가 없다면 타입도 제거.**

### 7. `app/strategies/rendering.ts` — RENDERING_SPECS 정리

synthesis, overview 항목을 제거한다 (DocumentType에서 제거한 경우).

### 8. 기타 참조 정리

제거한 도구/타입을 참조하는 곳을 검색하여 정리:

```
grep -r "evaluate_importance\|cluster_papers\|synthesize_topic\|translate_abstract\|find_related_papers" app/
grep -r "overview\|synthesis" app/ --include="*.ts" --include="*.tsx"
```

주요 확인 대상:
- `app/server/agent/orchestrator.ts` — post-action에서 제거 도구 참조
- `app/server/agent/system-prompt.ts` — 시나리오 프롬프트에서 도구 언급
- `app/components/` — overview/synthesis 렌더러 컴포넌트

## 검증

- [ ] `npm run build` 성공 (타입 에러 없음)
- [ ] 검색 → 검색 결과 문서 생성 정상
- [ ] 분석 → 분석 문서 생성 정상
- [ ] propose → 제안 카드 표시 + 승인/거부 동작 정상
- [ ] 제거한 도구가 시스템 프롬프트에 언급되지 않음
- [ ] 사이드바/워크스페이스에서 에러 없음
