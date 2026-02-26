# 사용자 기억 시스템 구현 프롬프트

> 코르카가 사용자를 기억하는 시스템을 구축한다. 온보딩 세션 + 사용자 프로파일 노드 + 매 턴 기억 추출.

## 배경

현재 기억 시스템(v3)은 fact/intention 노드를 세션 종료 시 배치 추출한다. 두 가지 구조적 문제가 있다:
- **케이스 4**: 재방문 시 "안녕하세요" 같은 짧은 인사 → 기억 활성화 실패 → 코르카가 맥락 없이 응답
- **케이스 5**: 노드 추출 지연 → 재방문을 첫 방문으로 오판

사용자에 대한 기억(프로파일/특성)을 user_id 기반으로 관리하면 두 문제 모두 해결된다.

개념 문서: `projects/lighthouse/user-memory-concept.md`

## 수행할 작업

### 1. 온보딩 세션 — 최초 입장 시 사용자 알아가기

최초 입장 시(research_journeys 0건 + experience_nodes 0개) 연구 주제로 바로 들어가지 않고, **사용자에 대해 알아가는 짧은 대화**를 먼저 한다.

`app/server/agent/system-prompt.ts`의 `FIRST_VISIT_SECTION`을 수정한다.

```
### 온보딩 — 코르카가 먼저 자기를 보여준다

사용자는 lighthouse에 처음 방문한 사람이다. "이 서비스 뭐지?" 상태이다.
코르카는 lighthouse의 관리자이자 연구 동료다.

**흐름: 자기소개 + 상대에 대해 묻기 — 대화의 기본**

사용자는 논문 리서치 도구라는 것을 알고 왔다. "어떻게 오셨어요?"는 부적절하다.
코르카가 자기를 소개하면서 서비스 맥락에 맞게 상대에 대해 묻는다.
- "안녕하세요, 저는 코르카예요. 함께 논문을 탐색하는 연구 동료입니다. 어떤 연구를 하고 계신가요?"
- 사용자가 답하면 대화를 이어가며 자연스럽게 파악한다

파악할 것 (대화 흐름 속에서):
1. **이름** — 자기소개의 일부로 자연스럽게
2. **소속과 역할** — 연구 맥락을 이해하기 위해
3. **연구 관심사** — 함께 탐색할 방향
4. **기대하는 것** — 어떤 도움이 필요한지

**자연스러운 것:**
- 자기소개하면서 상대에 대해 묻기 — 대화의 기본이다
- 상대 답변에 반응하면서 후속 질문 — 대화의 흐름이다
- 한 턴에 하나씩 자연스럽게 알아가기

**부자연스러운 것:**
- 질문을 연달아 나열 — 설문조사
- 정보 수집 의도가 드러나는 질문 패턴 — 면접
- 대화 맥락 없이 뜬금없이 개인정보 요청

**핵심: 좋은 첫 만남은 서로 소개하고, 왜 왔는지 이야기하고, 자연스럽게 함께 시작하는 것이다.**
```

### 2. 사용자 프로파일 노드 — DB 스키마

`memory_nodes`에 새로운 node_type `profile`을 추가한다.

```sql
-- 기존: node_type = 'fact' | 'intention'
-- 추가: node_type = 'profile'

-- profile 노드 예시:
-- content: "사용자의 이름은 김철수이다"
-- content: "사용자는 서울대 컴퓨터공학과 석사과정이다"
-- content: "사용자는 AI scientist 분야에 관심이 있다"
-- context_hint: 'user_profile'
```

profile 노드의 특성:
- `conversation_id = null` — 특정 대화에 종속되지 않음 (사전 기억과 동일)
- `context_hint = 'user_profile'` — 프로파일 그룹 식별
- `is_hub = false` — 일반 노드로 시작, 축적되면 허브 승격 검토

### 3. 온보딩 대화에서 프로파일 노드 추출

온보딩 대화 중 사용자가 자기 정보를 알려주면, 비동기로 profile 노드를 추출·저장한다.

추출 로직 (`app/server/memory/extract.ts` 신규 또는 기존 확장):

```
입력: 현재 턴의 사용자 메시지 + 코르카 응답
처리: LLM에게 "이 대화에서 사용자에 대해 새로 알게 된 사실이 있는가?" 판단 요청
출력: profile 노드 0~N개
저장: memory_nodes에 INSERT + 임베딩 계산
```

### 4. 매 턴 비동기 기억 추출

세션 종료 시 배치 추출 → **매 턴 비동기 추출**으로 전환한다.

`app/server/agent/orchestrator.ts`의 `handleChatTurn` 마지막에 fire-and-forget으로 추출을 실행한다.

```
handleChatTurn 흐름:
  1. parseAndPersistInput
  2. loadActivatedMemory
  3. buildPrompt
  4. streamLLM
  5. [신규] fire-and-forget: extractAndSaveNodes(턴 메시지)
     ├─ fact/intention 추출 (기존 로직 축소 적용)
     ├─ profile 추출 (사용자 정보 감지 시)
     ├─ 임베딩 계산
     └─ DB 저장
```

중복 방지:
- 추출 전 기존 노드와 임베딩 유사도 비교
- 유사도 > 0.95이면 스킵 (이미 있는 기억)
- 유사도 0.8~0.95이면 기존 노드 업데이트 검토

### 5. 재방문 시 사용자 기억 로드

`loadActivatedMemory`에 사용자 프로파일 로드를 추가한다.

```
loadActivatedMemory 수정:
  기존:
    1. activateMemory(queryText)    → spreading activation
    2. listRecentResearchDocuments  → 연구 문서
    3. countExperienceNodes         → 첫 방문 판단
    4. getLastConversationAt        → 시간 맥락

  추가:
    5. loadUserProfile(userId)      → profile 노드 전체 로드 (항상)

  isFirstVisit 판단 변경:
    기존: countExperienceNodes() === 0
    변경: conversations count === 0 (이전 대화 없음)

  프롬프트 주입:
    profile 노드는 항상 메모리 섹션 상단에 배치
    → 메시지 내용과 무관하게 사용자 맥락이 항상 존재
```

### 6. 특성 승격 (Promote) — 향후 확장

대화가 축적되면 fact에서 패턴을 발견하여 profile로 승격한다.
이 단계는 1차 구현에서 생략하고, 수동으로 프로파일을 관리한 경험이 쌓인 후 자동화한다.

```
예시:
  fact 3건: "AI scientist 검색", "AI scientist 분석", "AI scientist snowballing"
  → profile 승격: "사용자는 AI scientist 분야에 깊은 관심이 있다"
```

## 참조 파일

| 파일 | 변경 내용 |
|------|----------|
| `app/server/agent/system-prompt.ts` | FIRST_VISIT_SECTION → 온보딩 대화로 변경 |
| `app/server/agent/orchestrator.ts` | 매 턴 추출 + loadUserProfile 추가 |
| `app/server/memory/extract.ts` | 신규: 턴 단위 노드 추출 (fact + intention + profile) |
| `app/server/memory/activate.ts` | profile 노드 별도 로드 경로 추가 |
| `app/server/memory/prompt.ts` | 프로파일 섹션을 메모리 상단에 배치 |
| `supabase/migrations/` | node_type에 'profile' 추가 (CHECK 제약조건 수정) |

## 완료 기준

- [ ] 최초 입장 시 온보딩 대화 (이름, 소속, 관심사, 기대) 자연스럽게 진행
- [ ] 온보딩에서 파악한 정보가 profile 노드로 저장됨
- [ ] 매 턴 비동기로 fact/intention/profile 추출됨
- [ ] 재방문 시 profile 노드가 항상 프롬프트에 존재
- [ ] "안녕하세요"만 해도 코르카가 사용자를 인지하고 맥락 있게 반응
- [ ] isFirstVisit 판단이 conversations 수 기반으로 변경됨
- [ ] 기존 첫 방문(온보딩 완료 후 첫 연구) 흐름에 영향 없음
