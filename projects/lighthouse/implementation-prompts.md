# Light House 구현 프롬프트

> 각 단계를 독립 세션에서 실행한다. 순서대로 진행한다.
> 모든 단계에서 `docs/` 폴더의 설계 문서를 먼저 읽는다.

---

## Phase 1: 기반 구축

```
docs/ 폴더의 설계 문서를 모두 읽어라 (service-principles.md, SPEC.md, architecture.md, state-management.md, conventions.md).

이 프로젝트는 기존 검색 도구 패러다임에서 대화형 연구 동료 패러다임으로 전면 재설계한다.
이번 단계에서는 새 아키텍처의 기반을 구축한다. 기존 코드는 아직 건드리지 않는다.

수행할 작업:

1. 패키지 설치
   - `ai`, `@ai-sdk/google` (Vercel AI SDK + Gemini provider)
   - `@supabase/supabase-js` (Supabase 클라이언트)
   - `@supabase/ssr` (Next.js SSR 지원)

2. Supabase 테이블 생성 SQL 작성 (`supabase/migrations/` 폴더)
   - architecture.md §7 데이터 모델을 기반으로 한다
   - conversations: id, user_id, title, created_at, updated_at
   - messages: id, conversation_id, type(user/assistant/artifact/proposal/status), content(jsonb), created_at
   - artifacts: id, conversation_id, type, status, data(jsonb), parent_id, references(text[]), created_at, updated_at
   - research_journeys: id, conversation_id, user_id, memories(jsonb), created_at
   - RLS 정책: 모든 테이블에 user_id 기반 행 수준 보안
   - 외래키: messages.conversation_id → conversations.id, artifacts.conversation_id → conversations.id

3. 환경변수 설정
   - `.env.local.example` 파일 생성
   - NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY
   - SUPABASE_SERVICE_ROLE_KEY (서버사이드용)
   - GOOGLE_GENERATIVE_AI_API_KEY (Gemini)

4. Supabase 클라이언트 유틸 생성
   - `app/lib/supabase/client.ts` — 브라우저용
   - `app/lib/supabase/server.ts` — 서버용 (서비스 롤 키)

5. 새 디렉토리 구조 생성 (빈 폴더 + index.ts)
   - `app/server/agent/` — 상위 에이전트 설정
   - `app/server/tools/` — 하위 에이전트 도구 함수
   - `app/server/repository/` — 데이터 접근 계층
   - `app/domain/` — 공유 타입 (기존 domain/ 대체)

6. 도메인 타입 정의 (`app/domain/`)
   - architecture.md §4, §5, §7의 메시지 타입, 아티팩트 타입, 데이터 모델을 TypeScript 타입으로 정의
   - conventions.md의 판별 유니온 패턴을 따른다

완료 기준:
- `npm run build` 성공
- 새 디렉토리 구조 생성 완료
- 도메인 타입 정의 완료 (타입 체크 통과)
- Supabase migration SQL 파일 작성 완료
- `.env.local.example` 존재
```

---

## Phase 2: 대화 코어

```
docs/architecture.md §3(상위 에이전트), §4(대화 프로토콜)과 docs/SPEC.md §2(연구 동료), §4(대화 캔버스)를 읽어라.

이번 단계에서는 사용자와 동료가 텍스트로 대화할 수 있는 최소 기능을 구현한다.
아직 도구 호출(논문 검색 등)은 없다. 순수 대화만 동작하면 된다.

수행할 작업:

1. 상위 에이전트 시스템 프롬프트 작성 (`app/server/agent/system-prompt.ts`)
   - service-principles.md의 동료 원칙을 프롬프트로 변환
   - 정체성: "너는 Light House의 연구 동료이다. 사용자와 함께 학술 논문을 탐색한다"
   - 자율성 판단 기준 3가지 (되돌림 비용, 판단의 개인성, 맥락 전환 비용) 포함
   - 톤: 동료 레벨, ~다 체
   - 도구 정의는 이 단계에서는 비워둔다 (Phase 3에서 추가)

2. 채팅 API 라우트 (`app/api/chat/route.ts`)
   - Vercel AI SDK의 `streamText()` 사용
   - `@ai-sdk/google`의 `google('gemini-3-flash-preview')` 모델
   - 시스템 프롬프트 + 대화 히스토리 전달
   - SSE 스트리밍 응답

3. 메시지 저장/로드 (`app/server/repository/`)
   - Supabase에 대화 생성, 메시지 추가, 대화별 메시지 로드
   - 채팅 API에서 사용자 메시지와 동료 응답을 저장

4. 프론트엔드 대화 캔버스
   - 기존 Phase 기반 페이지(`(main)/page.tsx`, `explore/`)를 새 대화 페이지로 교체
   - AI SDK의 `useChat()` 훅 사용
   - SPEC.md §4의 레이아웃: 좌측 사이드바 + 중앙 대화 캔버스
   - 사이드바: 대화 목록 (Supabase에서 로드), 새 대화 버튼
   - 대화 영역: 메시지 목록 + 입력 바
   - URL: `/` (새 대화), `/chat/[conversationId]` (기존 대화)

5. 기존 코드 정리
   - 기존 Phase 기반 라우트 제거: `app/(main)/page.tsx`, `app/(main)/explore/`
   - 기존 stores/ 제거 (7개 스토어)
   - 기존 features/ 제거
   - 단, 기존 `lib/gemini.ts`, `lib/schemas.ts`, `api/` 안의 AI 호출 로직은 아직 보존 (Phase 3에서 추출)

완료 기준:
- 브라우저에서 대화 페이지 접속 가능
- 사용자가 메시지를 입력하면 동료가 스트리밍으로 응답
- 대화가 Supabase에 저장되고, 새로고침 후에도 복원
- 사이드바에서 대화 목록 표시, 대화 전환 가능
- 새 대화 생성 가능
```

---

## Phase 3: 도구 통합

```
docs/architecture.md §3(도구 등록, 자율성 결정)과 docs/SPEC.md §8(하위 에이전트 기능)을 읽어라.

이번 단계에서는 기존 API route의 핵심 로직을 추출하여 AI SDK 도구로 등록한다.
대화 중 동료가 "논문을 찾아볼게"라고 하면 실제로 검색이 실행되어야 한다.

수행할 작업:

1. 기존 코드에서 핵심 로직 추출
   기존 API route 안의 AI 호출 로직(프롬프트, Zod 스키마, 응답 파싱)을 순수 함수로 추출한다.
   참조할 기존 파일:
   - `api/search/route.ts` → Semantic Scholar API 호출 로직
   - `api/analyze/route.ts` → Gemini 논문 분석 프롬프트 + 파싱
   - `api/embed/route.ts` → OpenAI 임베딩 호출
   - `api/key-papers/route.ts` → 핵심 논문 선정 프롬프트
   - `api/cluster/route.ts` → 클러스터링 프롬프트
   - `api/topic-synthesis/route.ts` → 종합 분석 프롬프트
   - `api/translate/route.ts` → 번역 프롬프트
   - `lib/gemini.ts` → Gemini 클라이언트 (그대로 재사용)
   - `lib/schemas.ts` → Zod 스키마 (그대로 재사용)

2. 도구 함수 작성 (`app/server/tools/`)
   추출한 로직을 AI SDK tool 형식으로 감싼다. 하나의 도구 = 하나의 파일.
   - `search-papers.ts` — 논문 검색
   - `analyze-papers.ts` — 논문 분석 (요약, 방법론, 결과, 한계, 신뢰도)
   - `evaluate-importance.ts` — 중요도 평가 + 핵심 논문 선정
   - `cluster-papers.ts` — 클러스터링
   - `synthesize-topic.ts` — 종합 분석
   - `translate-abstract.ts` — 번역
   각 도구에 Zod 스키마로 파라미터를 정의한다.

3. 상위 에이전트에 도구 등록
   - `app/server/agent/tools.ts`에 도구 목록 정의
   - `app/api/chat/route.ts`의 `streamText()`에 tools 전달
   - 시스템 프롬프트에 각 도구의 용도와 기본 자율성 수준 안내 추가

4. 도구 실행 결과를 아티팩트로 저장
   - 검색 결과 → PaperCollection 아티팩트
   - 분석 결과 → PaperCard 아티팩트
   - Supabase artifacts 테이블에 저장

5. 기존 API route 정리
   - 핵심 로직 추출이 완료된 API route는 삭제
   - `lib/gemini.ts`, `lib/schemas.ts`는 유지

완료 기준:
- 대화 중 "transformer 추천 시스템 논문 찾아줘" → 동료가 search_papers 도구 호출 → 실제 검색 결과 반환
- 대화 중 "이 논문들 분석해줘" → 동료가 analyze_papers 호출 → 분석 결과 반환
- 도구 실행 결과가 Supabase에 아티팩트로 저장
- 기존 API route 폴더가 정리됨
```

---

## Phase 4: 아티팩트 시스템

```
docs/SPEC.md §6(연구 아티팩트), §4(인라인 아티팩트)와 docs/architecture.md §5(아티팩트 시스템)를 읽어라.

이번 단계에서는 도구 실행 결과를 대화 안에 구조화된 카드로 표시한다.
Phase 3에서 텍스트로만 반환되던 결과가 인라인 아티팩트로 렌더링되어야 한다.

수행할 작업:

1. 아티팩트 렌더러 컴포넌트
   SPEC.md §6의 각 아티팩트 유형별 렌더러를 만든다:
   - `PaperCardRenderer` — 논문 카드 (제목, 저자, AI 분석, 신뢰도 배지)
   - `PaperCollectionRenderer` — 논문 목록 (검색 결과, 클러스터)
   - `AnalysisReportRenderer` — 분석 리포트 (섹션별 내용 + 근거 논문 참조)
   각 렌더러는 접힘/펼침을 지원한다 (접힌 상태: 한 줄 요약)

2. 대화 메시지에 아티팩트 인라인 표시
   - 동료 응답에 `[artifact:id]` 마커가 포함되면 해당 아티팩트 렌더러로 치환
   - AI SDK의 커스텀 데이터 파트 또는 tool result를 활용하여 아티팩트 데이터를 전달

3. 아티팩트 생명주기 UI
   - creating: 스켈레톤 + "분석 중..." 표시
   - ready: 전체 렌더링
   - updating: 기존 내용 + "갱신 중..." 오버레이
   - 상태 전이는 SSE 이벤트로 수신

4. 아티팩트 저장/로드
   - Phase 3에서 만든 Supabase 저장 로직 활용
   - 대화 로드 시 해당 대화의 아티팩트도 함께 로드

5. Thinking HUD
   - 동료가 도구를 실행 중일 때 진행 상태를 표시
   - "📊 47편 분석 중... (12/47)" 형태
   - Emergency Stop 버튼 (도구 실행 취소)

완료 기준:
- 검색 결과가 대화 안에 논문 카드 목록으로 표시
- 분석 결과가 논문 카드에 AI 분석 섹션으로 표시 (신뢰도 배지 포함)
- 아티팩트 접기/펼치기 동작
- 도구 실행 중 Thinking HUD 표시 + 중단 가능
```

---

## Phase 5: 제안 카드 + 자율성

```
docs/SPEC.md §3(자율성 설계 지도), §5(제안 카드)와 docs/state-management.md(FSM)을 읽어라.

이번 단계에서는 동료가 다음 행동을 제안하고, 자율성 수준에 따라 승인 게이트를 적용한다.

수행할 작업:

1. 제안 카드 UI 컴포넌트
   SPEC.md §5의 구조를 따른다:
   - 제안 내용 + 근거 + 주도권 수준 + 행동 버튼(진행/대안/거부)
   - 대화 스트림 안에 인라인으로 표시
   - 사용자는 버튼 클릭 또는 자연어로 응답 가능

2. 자율성 수준별 동작 분기
   시스템 프롬프트를 강화한다:
   - L5 (자율): 도구를 호출하고 결과를 바로 통합. 제안 카드 없이 진행
   - L4 (승인): 도구를 실행하고 결과를 보여준 뒤 제안 카드로 "이 결과를 적용할까?" 승인 요청
   - L3 (자문): 실행 전에 제안 카드로 "이렇게 해볼까?" 제안. 승인 후 실행
   - L1-L2: 사용자가 명시적으로 요청할 때만 실행

3. FSM 게이트 구현
   state-management.md의 FSM 설계를 따른다:
   - 에이전트 실행 상태: IDLE → EXECUTING → AWAITING_APPROVAL → COMPLETED
   - AWAITING_APPROVAL에서 사용자 응답 없이 다음 전이 불가
   - 전이 함수 `canTransition()`으로 강제

4. 주도권 신호 UI
   SPEC.md §4의 주도권 신호:
   - 사용자 주도: 입력 바 활성
   - 동료 주도: Thinking HUD, 입력 바에 "동료 작업 중..."
   - 협력: 제안 카드 표시, 입력 바 활성

5. agentStore 구현
   state-management.md의 agentStore:
   - status: idle / thinking / executing / awaiting_approval
   - currentTask, pendingProposal, streamBuffer
   - cancelTask (Emergency Stop), respondToProposal

완료 기준:
- 동료가 클러스터링(L4)을 제안 카드로 제안 → 사용자 승인 → 실행
- 동료가 번역(L1)은 사용자가 요청할 때만 실행
- 동료가 분석(L5)은 제안 없이 자동 실행
- 주도권 신호가 에이전트 상태에 따라 변경
- Emergency Stop으로 실행 중인 작업 취소 가능
```

---

## Phase 6: 경험 기억

```
docs/SPEC.md §7(경험 기억)과 docs/architecture.md §6(기억 시스템)을 읽어라.

이번 단계에서는 동료가 연구 여정을 기억하고 세션 간에 맥락을 유지한다.
이것이 Light House의 핵심 차별점이다.

수행할 작업:

1. 기억 추출
   - 대화 종료(사용자가 새 대화를 시작하거나 떠날 때) 시 LLM을 호출하여 현재 대화에서 핵심 기억을 추출
   - 추출 프롬프트: "이 대화에서 다음 4가지를 추출하라: 탐색(어떤 주제를 찾아봤는가), 발견(의미 있는 결과), 판단(사용자의 결정), 방향 전환(탐색 방향 변경)"
   - 각 기억에 관련 아티팩트 ID를 연결
   - 결과를 Supabase research_journeys 테이블에 저장

2. 기억 주입
   - 새 대화 시작 시 해당 사용자의 최근 N개(예: 5개) 세션의 기억을 조회
   - 시스템 프롬프트에 기억을 주입:
     "이전 연구 여정:
      - [날짜] Transformer 추천 다양성: Chen 2024 핵심 발견, 방법론→응용 전환
      - [날짜] RLHF 안전성: 보상 모델 과적합 이슈 발견, ..."
   - 동료가 자연스럽게 이전 맥락을 활용하도록 프롬프트 안내

3. 기억 활용 대화
   - 동료가 "지난번에 이 저자를 중요하게 봤었는데..." 같은 발화를 할 수 있도록 시스템 프롬프트에 지시
   - 관련 주제가 나오면 이전 기억을 참조하여 연결

4. 사이드바 연구 여정 표시
   SPEC.md §7의 타임라인:
   - 각 대화 항목에 연구 여정의 핵심 흐름을 간략히 표시
   - 🔍 탐색, 📊 발견, 🔀 방향 전환, 📝 판단 아이콘

완료 기준:
- 대화 종료 시 기억이 자동 추출되어 Supabase에 저장
- 새 대화 시작 시 동료가 이전 맥락을 언급 ("지난번에 ...")
- 사이드바에 각 대화의 연구 여정 요약 표시
- "지난번에 이어서 하고 싶어" → 동료가 이전 기억 기반으로 연구 방향 제안
```
