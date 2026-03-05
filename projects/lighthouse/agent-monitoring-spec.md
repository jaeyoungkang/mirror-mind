# 에이전트 모니터링 명세

> 코르카의 의사결정을 추적·기록하는 시스템의 구조와 동작 정의

---

## 핵심 원칙

에이전트의 내부 상태를 명시화하면 두 가지가 동시에 풀린다:
1. **모니터링** — 뭘 판단했는지 보이니까 평가 가능
2. **행동 품질** — 명시적으로 생각하게 하면 판단 자체가 좋아짐 (chain-of-thought)

---

## 에이전트 상태 (AgentState)

매 턴 갱신되며, conversation metadata에 저장된다.

```typescript
interface AgentState {
  // 관계 수준 — 세션 간 carry (직전 세션에서 이월)
  relationshipLevel: 'initial' | 'forming' | 'trust' | 'deep';

  // 의도 파악
  intentClarity: 'unknown' | 'surface' | 'deep';
  detectedIntent: string | null;       // "AI Scientist 새 분야 탐색"

  // 전략
  scenarioType: number | null;         // 1~5 (research-scenarios 기준)
  approachStrategy: string | null;     // "Scoping Review", "Berry Picking" 등

  // 대화 단계
  conversationPhase:
    | 'greeting'          // 첫 인사
    | 'onboarding'        // 온보딩 (첫 방문)
    | 'intent_discovery'  // 의도 파악
    | 'exploration'       // 확산 탐색
    | 'convergence'       // 수렴 선별
    | 'deepening'         // 심화 분석
    | 'checkpoint'        // 중간 점검
    | 'conclusion';       // 결론/전환
}
```

### 상태 갱신 규칙

- **relationshipLevel**: 대화의 누적 경험으로 판단. 함께 어려운 문제를 풀거나, 실패 후 회복한 경험이 있어야 trust 이상
- **intentClarity**:
  - `unknown`: 사용자가 뭘 원하는지 아직 모름
  - `surface`: 표면적 요청은 파악 ("attention 논문 찾아줘")
  - `deep`: 연구 의도까지 파악 ("vision에서 linear attention 효율화로 제안서 준비")
- **scenarioType**: research-scenarios.md 기준 1~5. 확신 없으면 null 유지
- **approachStrategy**: 탐색 전략. 예: "Scoping Review", "Berry Picking", "Targeted Search"
- **conversationPhase**: 단계 간 의존 관계 있음 — 관계 형성이 이후 행동의 인식을, 의도 파악이 이후 도구 호출의 적절성 기준을 결정

### 생애주기

| 범위 | 항목 | 저장 위치 |
|------|------|----------|
| 세션 간 지속 | relationshipLevel | conversations.agent_state (다음 세션으로 carry) |
| 세션 내 지속 | intentClarity, detectedIntent, scenarioType, approachStrategy, conversationPhase | conversations.agent_state |
| 턴 단위 | toolChoiceReason, queryDesignReason, autonomyReason, nextPlan | turn_decisions |

---

## 턴별 의사결정 기록 (turn_decisions)

매 턴 에이전트의 판단 과정을 기록한다.

### 테이블 스키마

```sql
CREATE TABLE turn_decisions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  turn_index INTEGER NOT NULL,

  -- 에이전트 상태 스냅샷 (이 턴 시작 시점)
  agent_state_snapshot JSONB NOT NULL,

  -- 의사결정 기록
  tool_name TEXT,                      -- 선택한 도구 (null이면 도구 미사용)
  tool_choice_reason TEXT,             -- "탐색적 질문이라 넓은 검색부터"
  query_design_reason TEXT,            -- "AI Scientist + automated research로 핵심 키워드 조합"
  autonomy_reason TEXT,                -- "'찾아줘' 직접 동사 → propose 생략"
  next_plan TEXT,                      -- "결과 보고 핵심 5편 분석 제안할 것"

  -- 상태 변경 (이 턴 종료 후)
  agent_state_after JSONB,

  -- 실행 메타
  phases JSONB,                        -- 파이프라인 단계별 기록
  tool_calls JSONB,                    -- 도구 호출 상세 (input/output)
  duration_ms INTEGER,

  created_at TIMESTAMPTZ DEFAULT now()
);
```

### 기록 항목 설명

| 항목 | 용도 | 예시 |
|------|------|------|
| tool_choice_reason | 왜 이 도구를 선택/미선택했는가 | "대화로 의도 파악이 먼저" |
| query_design_reason | search 호출 시 쿼리 설계 이유 | "'AI Scientist'와 'hypothesis generation' 조합으로 핵심 동향 파악" |
| autonomy_reason | propose 사용/미사용 이유 | "구체적 검색 방향을 사용자에게 먼저 제안, L3 수준" |
| next_plan | 이 턴 이후 계획 | "검색 결과에서 핵심 논문 선별하여 분석 제안" |
| phases | 파이프라인 실행 트레이스 | parse-input → activate-memory → execute → post-action → dialogue |
| tool_calls | 도구 호출 상세 | input(query, limit), output(document id, title) |

---

## 동작 메커니즘

### `<agent-state>` 블록

LLM이 매 턴 응답 맨 앞에 `<agent-state>` JSON 블록을 출력한다. 시스템이 파싱하여 저장하고, 사용자에게는 표시하지 않는다.

```
<agent-state>
{
  "relationshipLevel": "initial",
  "intentClarity": "surface",
  "detectedIntent": "AI Scientist 분야 탐색",
  "scenarioType": 1,
  "approachStrategy": "Exploratory Conversation",
  "conversationPhase": "onboarding",
  "turnDecision": {
    "toolChoiceReason": "의도 파악이 먼저, 도구 사용 불필요",
    "queryDesignReason": null,
    "autonomyReason": "L2/L3 - 사용자 맥락 파악 후 검색 제안 예정",
    "nextPlan": "관심 지점 확인 후 검색 키워드 제안"
  }
}
</agent-state>
```

### 처리 흐름

1. LLM 응답에서 `<agent-state>` 블록 추출 (정규식)
2. JSON 파싱 + 스키마 검증 (실패 시 무시)
3. `conversations.agent_state` 갱신
4. `turn_decisions` 레코드 삽입
5. 응답에서 `<agent-state>` 블록 제거 후 사용자에게 전달

### 세션 시작 시 상태 초기화

1. 현재 conversation의 agent_state가 있으면 반환
2. 없으면 같은 사용자의 가장 최근 conversation에서 `relationshipLevel`만 carry
3. 그것도 없으면 기본값 (모두 initial/unknown/null)

---

## 평가 인프라

### session_evaluations 테이블

```sql
CREATE TABLE session_evaluations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  scores JSONB NOT NULL,               -- 차원별 0-3 점수 + 근거
  golden_scenario_id TEXT,             -- 비교한 골든 시나리오
  deviations JSONB,                    -- 이탈 지점 목록
  overall_summary TEXT,                -- 전체 평가 요약
  evaluator_model TEXT NOT NULL,       -- 평가에 사용한 LLM 모델
  turn_count INTEGER,
  created_at TIMESTAMPTZ DEFAULT now()
);
```

### /dev UI 구조

2단 레이아웃 — 좌측 세션 목록, 우측 상세 (3탭):

1. **의사결정 타임라인**: 턴별 카드 (상태 변화, 도구 호출, 이유, 계획)
2. **상태 흐름**: AgentState의 시간축 변화 시각화
3. **평가**: 수동 평가 실행 + 결과 표시

---

## 관련 문서

- 평가 체계: `projects/agent-decision-monitoring.md`
- 평가 프로세스: `projects/lighthouse/evaluation-process.md`
- 골든 시나리오: `projects/lighthouse/golden-scenarios.md`
- 연구 시나리오: `projects/lighthouse/research-scenarios.md`
- 서비스 원칙: `projects/lighthouse/service-principles.md`
