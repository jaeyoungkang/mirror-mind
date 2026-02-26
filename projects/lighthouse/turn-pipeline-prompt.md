# 도구 호출 파이프라인 구현 프롬프트

> 현재 단일 streamText 루프를 **3-Phase Turn Pipeline**으로 전환한다.
> 코드가 오케스트레이터, LLM은 실행자.

## 배경

현재 구조는 하나의 `streamText()` 호출이 9개 도구와 모든 연쇄 규칙을 관리한다.
도구 연쇄 규칙이 시스템 프롬프트 텍스트에만 존재하여 LLM이 따르지 않으면 막을 방법이 없다.

핵심 문제:
- search_papers → update_research_panel 후 LLM이 턴을 끝내버림 (대화 없이 문서만 생성)
- stepCountIs(5)로 복잡한 시나리오에서 step 부족
- 문서 생성과 대화가 분리되지 않음

## 아키텍처: 3-Phase Turn Pipeline

하나의 턴을 3개 phase로 분해한다.

```
Phase 1: Execute   — LLM이 도구 선택·실행 (maxSteps: 1)
Phase 2: Post      — 코드가 필수 후속 도구 자동 실행 (LLM 호출 없음)
Phase 3: Dialogue  — LLM이 결과 기반 대화 생성 (propose 자율 판단)
```

### Phase 흐름 다이어그램

```
사용자 메시지
  │
  ├─ Phase 1: streamText(tools: 메인 8개, maxSteps: 1)
  │   ├─ LLM이 텍스트 생성 + 도구 1개 실행
  │   ├─ propose 호출 시 → stopWhen → 턴 종료 (Phase 2,3 생략)
  │   └─ 도구 호출 없이 텍스트만 → 턴 종료 (Phase 2,3 생략)
  │
  ├─ Phase 2: 코드가 판단
  │   ├─ search_papers 실행됨 → searchResultsDoc로 upsertResearchDocument 호출
  │   ├─ find_related_papers 실행됨 → searchResultsDoc로 upsertResearchDocument 호출
  │   ├─ cluster_papers 실행됨 → 클러스터 데이터로 문서 생성 → upsertResearchDocument 호출
  │   └─ 그 외 → 스킵
  │
  └─ Phase 3: streamText(tools: propose만, maxSteps: 2)
      ├─ Phase 1,2 결과를 컨텍스트로 제공
      ├─ LLM이 결과 요약 + 인사이트 + 대화 이어가기
      └─ LLM이 필요하면 propose 호출 (자율 판단)
```

## 수행할 작업

### 1. Pipeline Rules 정의 — `app/server/agent/pipeline-rules.ts` (신규)

도구별 후속 동작 규칙을 코드로 정의한다.

```typescript
export interface PipelineRule {
  /** Phase 2에서 자동 실행할 후속 동작. null이면 Phase 2 스킵 */
  postAction: 'create-research-document' | null;
}

export const PIPELINE_RULES: Record<string, PipelineRule> = {
  search_papers:       { postAction: 'create-research-document' },
  find_related_papers: { postAction: 'create-research-document' },
  cluster_papers:      { postAction: 'create-research-document' },
  analyze_papers:      { postAction: null },
  evaluate_importance: { postAction: null },
  synthesize_topic:    { postAction: null },
  translate_abstract:  { postAction: null },
  propose:             { postAction: null },  // propose 시 Phase 2,3 생략
};
```

### 2. Post-Action 실행기 — `app/server/agent/post-actions.ts` (신규)

Phase 2에서 실행할 후속 동작을 구현한다.

```typescript
/**
 * Phase 1에서 실행된 도구의 결과를 받아 후속 동작을 실행한다.
 * LLM 호출 없이 코드만으로 처리한다.
 */
export async function executePostAction(
  toolName: string,
  toolResult: unknown,
  conversationId: string,
): Promise<PostActionResult | null>
```

search_papers, find_related_papers의 경우:
- 도구 결과에 `searchResultsDoc: { documentId, title, content }` 가 이미 포함되어 있다
- 이것을 그대로 `upsertResearchDocument()`에 전달한다

cluster_papers의 경우:
- 도구 결과의 `clusters`, `landscapeOverview`에서 마크다운 문서를 코드로 생성한다
- 클러스터별 섹션 + ```papers 코드블록 포함

반환값:
```typescript
interface PostActionResult {
  type: 'research-document-created';
  documentId: string;
  title: string;
}
```

### 3. Orchestrator 재구성 — `app/server/agent/orchestrator.ts` 수정

현재 `streamLLM()` 함수를 3-Phase Pipeline으로 교체한다.

**핵심 변경: `toUIMessageStreamResponse()` → `createDataStreamResponse()` + `mergeIntoDataStream()`**

AI SDK v6의 `createDataStreamResponse`로 여러 streamText 결과를 하나의 HTTP 스트림으로 연결한다.

```
import { createDataStreamResponse, streamText } from 'ai';

async function streamPipeline(
  conversationId: string,
  messages: UIMessage[],
  systemPrompt: string,
  turn: TurnContext,
): Promise<Response> {
  return createDataStreamResponse({
    execute: async (dataStream) => {
      // ─── Phase 1: Execute ───
      const phase1 = streamText({
        model: google("gemini-3-flash-preview"),
        system: systemPrompt,
        messages: await convertToModelMessages(sanitizeMessages(messages)),
        tools: createMainTools(conversationId, turn),  // propose 포함 8개
        maxSteps: 1,
        stopWhen: [hasToolCall("propose")],
        onStepFinish: (step) => turn.recordStep(step),
      });

      phase1.mergeIntoDataStream(dataStream);
      const phase1Result = await phase1;

      // ─── Phase 분기 판단 ───
      const executedTool = extractExecutedTool(phase1Result);

      // propose 호출 또는 도구 호출 없음 → 턴 종료
      if (!executedTool || executedTool === 'propose') {
        await persistResults(conversationId, phase1Result, null, null, messages, turn);
        return;
      }

      // ─── Phase 2: Post ───
      const postResult = await executePostAction(
        executedTool,
        extractToolResult(phase1Result),
        conversationId,
      );

      // ─── Phase 3: Dialogue ───
      const phase3System = buildPhase3System(systemPrompt, executedTool, postResult);
      const phase3Messages = buildPhase3Messages(messages, phase1Result, postResult);

      const phase3 = streamText({
        model: google("gemini-3-flash-preview"),
        system: phase3System,
        messages: phase3Messages,
        tools: { propose: createProposeTool() },  // propose만 제공
        maxSteps: 2,  // 텍스트 + 선택적 propose
        stopWhen: [hasToolCall("propose")],
        onStepFinish: (step) => turn.recordStep(step),
      });

      phase3.mergeIntoDataStream(dataStream);
      const phase3Result = await phase3;

      // ─── 영속화 ───
      await persistResults(conversationId, phase1Result, postResult, phase3Result, messages, turn);
    },
  });
}
```

### 4. Phase 3 컨텍스트 구성

Phase 3 LLM에게 Phase 1, 2 결과를 전달하는 방식.

**시스템 프롬프트 추가분** (`buildPhase3System`):
- Phase 1에서 실행된 도구와 결과 요약
- Phase 2에서 연구 문서가 생성되었다면 그 사실
- "도구 실행 결과를 바탕으로 사용자에게 자연스럽게 대화를 이어가라"

예시:
```
[실행 완료] search_papers("AI scientist")로 20편을 찾았습니다.
[자동 처리] 검색 결과를 연구 문서(document_id: search-xxx)에 정리했습니다.
사용자에게 결과를 요약하고, 인사이트를 공유하고, 다음 단계를 함께 정하세요.
연구 문서에 정리했다는 사실도 알려주세요.
```

**메시지 구성** (`buildPhase3Messages`):
- 원본 대화 히스토리 (messages)
- Phase 1의 assistant 텍스트 + tool_call + tool_result를 메시지로 포함
- Phase 3 LLM이 자연스럽게 이어서 대화

### 5. Tools 분리 — `app/server/agent/tools.ts` 수정

Phase 1용 도구 세트와 Phase 3용 도구 세트를 분리한다.

```typescript
/** Phase 1: 메인 도구 (update_research_panel 제거) */
export function createMainTools(conversationId: string, turn?: TurnContext) {
  const raw = {
    search_papers: createSearchPapersTool(conversationId),
    analyze_papers: createAnalyzePapersTool(conversationId),
    evaluate_importance: createEvaluateImportanceTool(),
    cluster_papers: createClusterPapersTool(conversationId),
    synthesize_topic: createSynthesizeTopicTool(conversationId),
    translate_abstract: createTranslateAbstractTool(),
    propose: createProposeTool(),
    find_related_papers: createFindRelatedPapersTool(conversationId),
    // update_research_panel 제거 — Phase 2에서 코드가 처리
  };
  if (!turn) return raw;
  return wrapToolsWithObservation(raw, turn);
}
```

**update_research_panel은 Phase 1 도구에서 제거한다.**
- 이 도구는 더 이상 LLM이 호출하지 않는다
- Phase 2에서 코드가 직접 `upsertResearchDocument()`를 호출한다
- 도구 파일(`update-research-panel.ts`)은 유지하되, LLM 도구 등록에서만 빠진다

### 6. 시스템 프롬프트 경량화 — `app/server/agent/system-prompt.ts` 수정

도구 연쇄 규칙이 코드로 이동했으므로 시스템 프롬프트에서 제거/수정한다.

**제거할 섹션:**
- "필수 규칙 — update_research_panel 호출은 예외 없이 의무" (193-201줄) — 코드가 처리
- "도구 연쇄 추가 허용" (223-226줄) — 코드가 처리
- "update_research_panel 자율성" (219-221줄) — 코드가 처리
- "문서 생성 안내 의무" (203-209줄) — Phase 3 컨텍스트로 이동

**수정할 섹션:**
- "도구 연쇄 호출 규칙" — "한 턴에 하나의 도구" 규칙으로 단순화 (코드가 강제하므로 maxSteps: 1)
- "연구 문서 패널 활용" — update_research_panel 관련 제거, ```papers 형식과 문서 구성만 유지
- "검색 후 행동 규칙" — 제거 (Phase 3 컨텍스트로 이동)

**추가할 내용:**
- "도구를 실행하면 시스템이 자동으로 연구 문서를 생성하고, 이어서 대화를 요청한다. 결과를 요약하고 인사이트를 공유하라."

### 7. 클라이언트 스트림 호환성 확인

`toUIMessageStreamResponse()` → `createDataStreamResponse()` 전환 시 클라이언트 호환성을 확인한다.

확인할 파일: `app/components/NotebookCanvas.tsx`의 useChat hook

AI SDK v6의 `useChat` + `DefaultChatTransport`는 data stream 프로토콜을 지원한다.
만약 호환 문제가 있으면:
- `DefaultChatTransport` 대신 명시적으로 data stream transport 사용
- 또는 `toDataStreamResponse()` 사용 (같은 프로토콜의 다른 이름)

### 8. 영속화 통합 — `persistResults` 함수

현재 `onFinish` 콜백에서 처리하던 영속화를 별도 함수로 추출한다.

```typescript
async function persistResults(
  conversationId: string,
  phase1Result: StreamTextResult,
  postResult: PostActionResult | null,
  phase3Result: StreamTextResult | null,
  messages: UIMessage[],
  turn: TurnContext,
) {
  // 1. 모든 phase의 텍스트와 도구 호출을 합쳐서 하나의 assistant 메시지로 저장
  const allText = [phase1Result.text, phase3Result?.text].filter(Boolean).join('\n');
  const allToolParts = [
    ...extractToolParts(phase1Result),
    ...extractToolParts(phase3Result),
  ];

  await appendMessage({
    conversationId,
    type: "assistant",
    text: allText,
    toolParts: allToolParts.length > 0 ? allToolParts : undefined,
  });

  turn.finalize();

  // 2. 비동기 기억 추출
  const userText = extractLastUserText(messages);
  if (userText || allText) {
    extractAndSaveTurnNodes(conversationId, userText, allText)
      .catch((err) => console.error("[memory] 턴 추출 실패:", err));
  }
}
```

### 9. 클라이언트 패널 동기화

현재 `UpdateResearchPanelResult` 컴포넌트가 패널 동기화를 담당한다.
Phase 2에서 코드가 직접 upsert하므로, 클라이언트에 결과를 전달하는 방식이 필요하다.

**방법: `dataStream.writeData()`로 커스텀 이벤트 전송**

서버:
```typescript
// Phase 2에서 문서 생성 후
dataStream.writeData({
  type: 'research-document-updated',
  documentId: postResult.documentId,
  title: postResult.title,
  content: postResult.content,
});
```

클라이언트: `useChat`의 `onData` 또는 `useDataStream` 콜백에서 패널 store 동기화.

확인 필요: AI SDK v6에서 `createDataStreamResponse`의 `writeData`와 클라이언트 수신 방법의 정확한 API.

**대안**: `SearchPapersResult` 컴포넌트가 이미 `searchResultsDoc`으로 기본 패널 동기화를 한다. Phase 2의 upsert는 DB 영속화만 담당하고, 클라이언트 패널은 Phase 1의 search_papers 결과에서 자동 동기화되는 것으로 충분할 수 있다. 이 경우 추가 클라이언트 코드 불필요.

## 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `app/server/agent/orchestrator.ts` | streamLLM → streamPipeline 교체. createDataStreamResponse 도입. 3-Phase 흐름 |
| `app/server/agent/pipeline-rules.ts` | **신규**. 도구별 후속 동작 규칙 정의 |
| `app/server/agent/post-actions.ts` | **신규**. Phase 2 후속 동작 실행기 (upsertResearchDocument 호출) |
| `app/server/agent/tools.ts` | createMainTools 추가 (update_research_panel 제외 세트) |
| `app/server/agent/system-prompt.ts` | 도구 연쇄 규칙 제거, Phase 3 대화 지시 추가 |
| `app/components/NotebookCanvas.tsx` | createDataStreamResponse 호환 확인 (변경 최소) |

## 완료 기준

- [ ] search_papers 실행 후 연구 문서가 **반드시** 생성된다 (코드 보장)
- [ ] 연구 문서 생성 후 대화가 **반드시** 이어진다 (Phase 3 보장)
- [ ] LLM이 propose를 자율적으로 판단하여 호출하거나 하지 않는다
- [ ] propose 없이 순수 대화만으로 턴이 끝나는 경우도 정상 동작
- [ ] 기존 시연 시나리오(첫 만남, 재방문, 검색→분석→구조화) 정상 동작
- [ ] 스트리밍이 끊기지 않고 클라이언트에서 연속된 하나의 응답으로 보인다
- [ ] stepCountIs(5) 제약 해소 — Phase별 독립 호출로 step 부족 문제 없음

## 참조

- 현재 orchestrator: `app/server/agent/orchestrator.ts`
- 현재 tools: `app/server/agent/tools.ts`
- 현재 system-prompt: `app/server/agent/system-prompt.ts`
- update_research_panel: `app/server/tools/update-research-panel.ts`
- search_papers searchResultsDoc: `app/server/tools/search-papers.ts:73-101`
- find_related_papers searchResultsDoc: `app/server/tools/find-related-papers.ts`
- 클라이언트 useChat: `app/components/NotebookCanvas.tsx`
- 클라이언트 패널 동기화: `app/components/artifacts/renderers/UpdateResearchPanelResult.tsx`
- AI SDK imports: `ai` 패키지 — `createDataStreamResponse`, `mergeIntoDataStream`, `streamText`
