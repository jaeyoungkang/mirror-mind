# AI Scientist 시드 노드 추가 프롬프트

> 코르카가 AI scientist 분야에 대한 사전 연구 경험을 갖도록 시드 노드를 추가한다.

## 배경

시연에서 코르카가 AI scientist 주제로 대화할 때, 이미 이 분야를 탐색해본 경험이 있으면 훨씬 자연스러운 동료 경험이 된다. 일반 AI 도구는 이런 축적된 맥락이 없다.

사전 기억(conversation_id=null)으로 추가하여, 프롬프트에서 "(사전 지식)"으로 표시되게 한다.

## 수행할 작업

### 1. DB 마이그레이션

`supabase/migrations/00010_ai_scientist_seed_nodes.sql`:

```sql
-- AI scientist 분야 사전 연구 경험 노드 추가
-- conversation_id = null (사전 기억), is_hub = false (일반 노드)

INSERT INTO memory_nodes (user_id, conversation_id, content, node_type, context_hint, is_hub)
VALUES
-- 분야 개관
('00000000-0000-0000-0000-000000000000', null,
 'AI scientist 분야를 탐색한 적이 있다. 이 분야는 크게 세 방향으로 나뉜다: (1) 자동 가설 생성 및 실험 설계, (2) 자동 논문 작성 및 리뷰, (3) 과학적 발견을 위한 LLM 에이전트. 2023년 이후 급성장 중이다.',
 'fact', 'AI scientist 연구 경험', false),

-- 핵심 논문/시스템
('00000000-0000-0000-0000-000000000000', null,
 'Sakana AI의 "The AI Scientist" (2024)가 이 분야의 대표적 논문이다. 연구 아이디어 생성부터 실험 실행, 논문 작성, 피어 리뷰까지 전 과정을 자동화하는 시스템을 제안했다. NeurIPS 2024에서 큰 주목을 받았다.',
 'fact', 'AI scientist 연구 경험', false),

('00000000-0000-0000-0000-000000000000', null,
 'DeepMind의 FunSearch (2023)는 LLM과 진화 알고리즘을 결합하여 새로운 수학적 발견을 한 사례다. 조합론의 cap set 문제에서 기존 최고 기록을 경신했다. LLM이 코드를 생성하고 평가 함수가 검증하는 구조였다.',
 'fact', 'AI scientist 연구 경험', false),

('00000000-0000-0000-0000-000000000000', null,
 'ChemCrow (2023)는 화학 분야에서 LLM 에이전트가 도구를 사용하여 분자 설계, 합성 경로 탐색 등을 수행하는 시스템이다. 도메인 특화 도구와 LLM의 결합이 핵심이었다.',
 'fact', 'AI scientist 연구 경험', false),

-- 연구 방향별 특징
('00000000-0000-0000-0000-000000000000', null,
 '자동 가설 생성 연구에서 핵심 쟁점은 novelty 검증이다. LLM이 생성한 가설이 정말 새로운 것인지, 기존 연구의 재조합인지 판단하기 어렵다. 이를 위해 문헌 검색 기반 novelty check 방법이 제안되고 있다.',
 'fact', 'AI scientist 연구 경험', false),

('00000000-0000-0000-0000-000000000000', null,
 '자동 논문 리뷰 연구에서는 GPT-4와 인간 리뷰어의 일치도가 약 50~60% 수준이라는 결과가 있었다. 아직 전문가를 대체하기는 어렵지만, 초기 스크리닝이나 형식 검토에는 활용 가능성이 있다.',
 'fact', 'AI scientist 연구 경험', false),

('00000000-0000-0000-0000-000000000000', null,
 'AI scientist 분야의 공통적 한계는 실험 검증의 신뢰성이다. 코드를 생성하고 실행할 수 있지만, 실험 결과가 의미 있는지 판단하는 것은 여전히 인간 연구자의 역할이다. 자동화의 범위와 인간 검증의 경계가 활발히 논의되고 있다.',
 'fact', 'AI scientist 연구 경험', false),

-- 관련 키워드/용어
('00000000-0000-0000-0000-000000000000', null,
 'AI scientist 분야는 다양한 이름으로 불린다. "automated scientific discovery", "AI for science", "LLM-driven research", "autonomous research agent" 등이 비슷한 맥락에서 사용된다. 검색 시 용어 변이에 주의해야 한다.',
 'fact', 'AI scientist 연구 경험', false);
```

### 2. 임베딩 계산 및 네트워크 구축

마이그레이션 적용 후 기존 seed-embeddings 스크립트를 실행한다:

```bash
npx tsx scripts/seed-embeddings.ts
```

이 스크립트는 임베딩이 없는 노드만 찾아서 처리하므로, 새로 추가된 8개 노드만 임베딩이 계산되고 네트워크에 연결된다.

## 참조 파일

| 파일 | 역할 |
|------|------|
| `supabase/migrations/00008_seed_memory_nodes.sql` | 기존 48개 시드 노드 (형식 참조) |
| `supabase/migrations/00009_memory_hub_nodes.sql` | 마지막 마이그레이션 (번호 참조) |
| `scripts/seed-embeddings.ts` | 임베딩 계산 + 네트워크 구축 스크립트 |

## 주의사항

- 새 노드는 `is_hub = false`다. AI scientist 지식은 허브가 아닌 일반 시드 노드다.
- `context_hint = 'AI scientist 연구 경험'`으로 통일하여 그룹화한다.
- 노드 내용은 코르카 1인칭 시점이다 ("탐색한 적이 있다", "핵심 쟁점은...").
- 마이그레이션 번호는 00010이다 (00009가 마지막).

## 완료 기준

- [ ] 8개 AI scientist 시드 노드가 DB에 추가됨
- [ ] 임베딩 계산 완료 + 네트워크 연결됨
- [ ] "AI scientist" 관련 대화 시 해당 기억이 spreading activation으로 활성화됨
- [ ] 기존 48개 시드 노드에 영향 없음
