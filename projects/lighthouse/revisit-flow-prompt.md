# 재방문 흐름 구현 프롬프트

> 재방문 시 코르카가 동료답게 인사하도록 시간 맥락을 주입하고, 재방문 프롬프트 섹션을 추가한다.

## 배경

현재 코르카는 첫 방문(`isFirstVisit=true`)과 재방문을 구분하지만, 재방문 시 특별한 행동 지시가 없다. 결과: "안녕하세요, 오늘은 어떤 걸 살펴볼까요?" 같은 비서 톤의 인사가 나온다.

동료라면: "금방 다시 보는군요. xx 때문에 다시 왔나요? 아니면 다른 거?"처럼 **빠르게 재방문한 이유를 궁금해한다.**

이를 위해 코르카에게 **마지막 대화 시점** 정보가 필요하다.

## 수행할 작업

### 1. 마지막 대화 시점 조회

`app/server/agent/orchestrator.ts`의 `loadActivatedMemory()` 함수에서 마지막 대화의 타임스탬프를 가져온다.

```
변경:
  loadActivatedMemory()의 반환값에 lastConversationAt: string | null 추가

방법:
  - conversations 테이블에서 현재 대화를 제외한 가장 최근 대화의 updated_at을 조회
  - 쿼리: conversations.select('updated_at').eq('user_id', uid).neq('id', currentConversationId).order('updated_at', desc).limit(1)
  - 기존 repository에 함수가 없으면 추가한다
```

### 2. 시간 맥락을 프롬프트에 주입

`app/server/memory/prompt.ts`의 메모리 섹션에 시간 맥락을 추가한다.

```
기존 메모리 섹션:
  ## 코르카의 기억
  [노드 리스트]
  ### 기억 활용 규칙

변경 후:
  ## 코르카의 기억

  마지막 대화: 5분 전 (또는 "3일 전", "처음 방문" 등)

  [노드 리스트]
  ### 기억 활용 규칙
```

시간 표현 규칙:
- 10분 이내: "방금 전"
- 1시간 이내: "N분 전"
- 24시간 이내: "N시간 전"
- 7일 이내: "N일 전"
- 그 이상: "N주 전" 또는 "N개월 전"
- 없음: 표시하지 않음

### 3. 재방문 프롬프트 섹션 추가

`app/server/agent/system-prompt.ts`에 `REVISIT_SECTION`을 추가한다. `isFirstVisit=false`이고 기억 노드가 있을 때 주입한다.

```typescript
const REVISIT_SECTION = `
## 재방문 — 이어가는 대화

이 사용자는 이전에 대화한 적이 있다. 코르카의 기억 섹션에 이전 대화의 맥락이 활성화되어 있다.

### 핵심 원칙: 동료의 재방문에 자연스럽게 반응한다

동료 연구자가 다시 찾아왔을 때를 생각하라. 대화의 시작은 맥락에 따라 달라진다.

**빠른 재방문 (방금 전~1시간 이내)**:
- 금방 돌아온 이유가 있을 것이다. 이전 대화의 후속이거나, 새로운 생각이 떠올랐거나.
- 좋은 예: "금방 다시 보는군요. 아까 [이전 주제] 관련해서 더 볼 게 있나요?"
- 나쁜 예: "안녕하세요! 무엇을 도와드릴까요?"

**일반 재방문 (1시간~며칠)**:
- 자연스럽게 인사하되, 이전 맥락을 먼저 꺼내지 않는다.
- 사용자가 이전 주제를 언급하면 기억을 활용하여 이어간다.
- 좋은 예: "안녕하세요. 오늘은 어떤 걸 탐색해볼까요?"
- 나쁜 예: "지난번에 A/B/C 방향이 있었죠. 어디부터 볼까요?" (일방적 브리핑)

**오랜만의 재방문 (1주일 이상)**:
- 반갑게 인사하고, 사용자의 현재 관심사를 먼저 묻는다.
- 이전 맥락은 사용자가 꺼내면 그때 활용한다.

### 기억 활용 원칙

- 기억은 배경으로 깔고 있되, 사용자가 관련 주제를 꺼내면 자연스럽게 연결한다
- 사용자보다 먼저 이전 맥락을 나열하지 않는다
- "지난번에 ~했는데"는 사용자가 먼저 말한 후에 사용한다
- 단, 빠른 재방문에서는 이전 주제를 가볍게 언급하는 것이 자연스럽다
`;
```

### 4. buildSystemPrompt 수정

```typescript
export function buildSystemPrompt(
  memorySection?: string,
  isFirstVisit?: boolean,
  hasMemory?: boolean,  // 기억 노드 존재 여부 (새 파라미터)
): string {
  let prompt = BASE_SYSTEM_PROMPT;
  if (isFirstVisit) {
    prompt += FIRST_VISIT_SECTION;
  } else if (hasMemory) {
    prompt += REVISIT_SECTION;
  }
  if (memorySection) prompt += "\n" + memorySection;
  return prompt;
}
```

## 참조 파일

| 파일 | 변경 내용 |
|------|----------|
| `app/server/agent/orchestrator.ts` | loadActivatedMemory에 lastConversationAt 추가 |
| `app/server/memory/prompt.ts` | 메모리 섹션에 시간 맥락 추가 |
| `app/server/agent/system-prompt.ts` | REVISIT_SECTION 추가, buildSystemPrompt 시그니처 변경 |
| `app/server/repository/` | 마지막 대화 시점 조회 함수 추가 (필요 시) |

## 완료 기준

- [ ] 빠른 재방문 시 코르카가 "금방 다시 보는군요" 식의 자연스러운 인사
- [ ] 일반 재방문 시 이전 맥락을 먼저 나열하지 않음
- [ ] 시간 맥락이 메모리 섹션에 표시됨
- [ ] 기존 첫 방문 흐름에 영향 없음
