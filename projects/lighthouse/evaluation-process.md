# Lighthouse 평가 프로세스

> 코르카가 좋은 연구 동료로서 행동했는가를 검증하는 실행 절차

평가 체계 설계: `projects/agent-decision-monitoring.md`

---

## 실행 방식

**수동 트리거 (B 방식)** — 특정 세션을 골라 평가 실행

---

## 데이터 소스

| 테이블 | 용도 | 핵심 컬럼 |
|--------|------|-----------|
| `messages` | 대화 전문 | type, content, conversation_id |
| `turn_decisions` | 턴별 의사결정 기록 | agent_state_snapshot, tool_choice_reason, query_design_reason, autonomy_reason, next_plan, tool_calls, phases |
| `documents` | 생성된 문서 | type(search/analysis/collection/discussion), title, content |
| `conversations` | 세션 메타 | id, title, created_at |

---

## 평가 프로세스

### Step 1. 세션 데이터 추출

대상 세션의 messages + turn_decisions + documents를 수집한다.

```
입력: conversation_id
출력: { messages[], turnDecisions[], documents[] }
```

### Step 2. 대화 단계 식별 (계층 6)

turn_decisions의 `agent_state_snapshot.conversationPhase`로 단계를 식별한다.

```
관계 형성 → 의도 파악 → 확산 → 수렴 → 심화 → 점검 → 결론
```

**의존 관계 판정:**
- 관계 형성 점수가 낮으면 → 이후 행동의 "인식"이 달라졌을 가능성 기록
- 의도 파악 점수가 낮으면 → 이후 도구 호출 평가에 "의도 미파악 상태" 맥락 부여

### Step 3. 턴별 평가 (계층 1~3)

각 턴에 대해 3개 차원을 평가한다.

**1. 도구 선택·실행**
- tool_choice_reason과 실제 tool_calls 대조
- 선택 정확성, 순서 적절성, 파라미터 품질, 불필요 호출, 누락

**2. 대화 품질**
- 응답 텍스트 기반: 맥락 유지, 탐구성, 정보성, 개입 타이밍, 투명성, 자연스러움

**3. 협업 적절성**
- autonomy_reason + propose 사용 패턴
- 지원 vs 대체, 확신도 전달, 주도권 균형, 진행도

### Step 4. 서비스 특화 평가 (계층 4~5)

**4. Lighthouse 특화**
- agent_state의 scenarioType, intentClarity, approachStrategy 활용
- 연구 의도 파악, 역할 분담 제안, 자율성 수준(L1~L5), 시나리오 인지, 톤, 문서 품질

**5. 도구별 사용 품질**

| 도구 | 평가 기준 |
|------|----------|
| search_papers | 쿼리가 의도에 맞는가, 키워드 조합, 실패 시 전략 전환 |
| analyze_papers | 대상 선정 적절성, 핵심 논문 선별, 분석 깊이 |
| propose | 타이밍, 내용 적절성, 근거 유무 |

### Step 5. 골든 시나리오 비교

사전 정의된 이상적 흐름과 실제 trajectory를 대조한다.

**골든 시나리오 A: AI Scientist (시나리오 1 — 새 분야 진입)**
- 관계 형성 → 의도 파악(2~3턴) → propose로 검색 확인 → 검색 → 핵심 선별 → 분석 제안 → 분석 → 구조화 → 점검

**골든 시나리오 B: Attention (시나리오 2 — 제안서 준비)**
- 의도 파악(1턴, 직접 동사 인지) → 즉시 검색 → 트리아지 → 병렬 분석 → 갭 발견 → 확장 검색 → 점검

비교 결과:
- 이탈 지점(deviation point) 식별
- Progress Rate (기대 단계 대비 달성도)
- Minefields 회피 여부

### Step 6. 종합 리포트

```
세션: {conversation_id}
날짜: {created_at}
턴 수: {N}
도달 단계: {마지막 conversationPhase}

[계층 6] 대화 단계별
  관계 형성:  ?/3 — {근거}
  의도 파악:  ?/3 — {근거}
  확산:      ?/3 — {근거}
  수렴:      ?/3 — {근거}
  ...

[계층 1~3] 턴별 평균
  도구 선택:  ?/3
  대화 품질:  ?/3
  협업:      ?/3

[계층 4] Lighthouse 특화
  연구 의도:  ?/3
  자율성:    ?/3
  시나리오:  ?/3
  톤:       ?/3
  문서 품질:  ?/3

[계층 5] 도구별
  search:   ?/3
  analyze:  ?/3
  propose:  ?/3

[골든 시나리오 비교]
  Progress Rate: ?%
  이탈 지점: {턴 N에서 X를 했어야 하는데 Y를 함}

[개선 제안]
  1. ...
  2. ...
```

---

## 채점 기준 (0~3)

| 점수 | 의미 |
|------|------|
| 3 | 이상적 — 골든 시나리오 수준 |
| 2 | 적절 — 기본은 되지만 개선 여지 |
| 1 | 부족 — 핵심을 놓침 |
| 0 | 부적절 — 맥락에 맞지 않는 행동 |

---

## 실행 방법

```bash
# 1. 세션 목록 확인
curl -s "http://127.0.0.1:54321/rest/v1/conversations?select=id,title,created_at&order=created_at.desc" \
  -H "apikey: $SRK" -H "Authorization: Bearer $SRK"

# 2. 대상 세션의 데이터 추출
# messages, turn_decisions, documents를 conversation_id로 조회

# 3. 브로콜리에게 평가 요청
# "이 세션 데이터를 evaluation-process.md 기준으로 평가해줘"
```
