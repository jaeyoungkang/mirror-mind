# 사용자 기억 (User Memory) — 개념 정의

## 핵심 질문
> "코르카는 이 사용자를 얼마나 잘 아는가?"

## 배경

### 심리학: Person Memory
사람에 대한 기억은 두 층으로 구성된다:
- **특성 표상 (trait)** — 추론된 성격/특징. "이 사람은 꼼꼼하다", "새 분야 탐색을 좋아한다"
- **에피소드 표상 (episode)** — 구체적 행동/사건. "이 사람이 X라고 말했다"

핵심 발견:
- 특성이 에피소드를 조직화한다 — 특성이 있으면 관련 에피소드가 더 잘 회상된다
- 불일치 정보를 더 잘 기억한다 — 기존 인상과 모순되는 행동이 더 풍부한 연결 네트워크를 만든다
- 친숙해질수록 상대의 의도를 예측한다

### AI 에이전트 설계 패턴
- **Mem0**: Capture → Promote → Retrieve. 대화에서 사용자 메모리로 승격
- **Letta**: Core Memory — 항상 컨텍스트에 존재하는 사용자 정보. 에이전트가 스스로 편집 가능

### 참고 문헌
- [Nature Reviews Psychology — Impression formation and updating](https://www.nature.com/articles/s44159-025-00445-x)
- [Encyclopedia.com — Person Memory](https://www.encyclopedia.com/social-sciences/applied-and-social-sciences-magazines/person-memory)
- [Memory in the Age of AI Agents (Survey)](https://arxiv.org/abs/2512.13564)
- [Letta — Agent Memory](https://www.letta.com/blog/agent-memory)
- [Mem0 — Memory Types](https://docs.mem0.ai/core-concepts/memory-types)

---

## 현재 v3 기억 시스템과의 갭

| v3 현재 | 빠진 것 |
|---------|---------|
| **fact** — "사용자가 X라고 말했다" (에피소드) | **사용자 특성** — "이 사용자는 AI에 관심 있다" (trait) |
| **intention** — "나는 ~하려 했다" | **사용자 상태** — "탐색 초기 단계다" |
| 메시지 기반 활성화 | **user_id 기반 활성화** |

fact은 "무슨 일이 있었는가"이고, 사용자 기억은 "이 사람이 누구인가"이다.

---

## 사용자 기억의 구성

### 1. 프로파일 (명시적 — 사용자가 직접 알려줌)
- 이름
- 소속 / 역할 (대학원생, 연구원, 엔지니어 등)
- 연구 분야 / 관심 영역
- 코르카에게 기대하는 것

### 2. 특성 (추론적 — 대화에서 관찰)
- 대화 스타일 선호 (직접적 / 탐색적)
- 연구 성숙도 (입문 / 숙련)
- 의사결정 패턴 (빠른 결정 / 숙고형)
- 관심 주제의 변화 궤적

### 3. 관계 (축적적 — 상호작용에서 형성)
- 함께 탐색한 주제들
- 코르카의 제안에 대한 반응 패턴
- 신뢰 수준 (처음 / 익숙 / 깊은 협력)

---

## 기억 형성 과정

```
[온보딩 세션]
사용자가 직접 알려줌 → 프로파일 노드 생성

[매 턴 비동기 추출]
대화에서 fact/intention 추출 (기존)
+ 사용자 특성 추론 (신규)

[승격 (Promote)]
fact 축적 → 패턴 발견 → 특성 노드로 승격
예: "AI scientist 논문 3번 검색" → "AI scientist 분야에 관심 있다"

[활성화]
재방문 시: user_id → 프로파일 + 최근 특성 → 항상 컨텍스트에 존재
메시지 기반: spreading activation → 관련 fact/intention 추가 활성화
```

---

## 해결하는 문제

| 문제 | 해결 방식 |
|------|----------|
| 케이스 4 (인사 → 활성화 실패) | user_id 기반으로 프로파일/특성 노드 항상 로드 |
| 케이스 5 (노드 추출 지연 → 오판) | 매 턴 추출으로 실시간 축적 |
| 재방문 시 "이 사람 누구?" | 프로파일이 항상 배경에 있음 |
| 관계 깊이별 행동 변화 | 관계 노드 축적으로 신뢰 수준 판단 가능 |
