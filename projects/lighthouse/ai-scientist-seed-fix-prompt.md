# AI Scientist 시드 노드 수정 프롬프트

> 검증 결과 사실 오류 2건 + 보강 6건 + 추가 3건. 기존 8개 노드를 UPDATE하고 3개를 INSERT한다.

## 배경

기존 `00010_ai_scientist_seed_nodes.sql`로 추가된 8개 시드 노드의 사실 관계를 검증한 결과:
- **사실 오류 2건**: 노드 2(Sakana AI — "NeurIPS 2024 발표"는 거짓, arXiv 프리프린트), 노드 6(리뷰 일치도 — "50~60%"는 부정확, 실제 30~39%)
- **보강 필요 6건**: 출판 정보, 구체적 성과, 최신 용어 등
- **누락 3건**: 2024~2025년 주요 발전 (Google AI co-scientist, AlphaFold 노벨상, FutureHouse Robin)

## 수행할 작업

### 1. DB 마이그레이션

`supabase/migrations/00011_fix_ai_scientist_seed_nodes.sql`:

```sql
-- AI scientist 시드 노드 수정 (검증 반영)
-- context_hint = 'AI scientist 연구 경험' 노드를 content 기준으로 UPDATE

-- 노드 1: 분야 개요 — 분류 보완, 시점 정확화
UPDATE memory_nodes
SET content = 'AI scientist 분야를 탐색한 적이 있다. 이 분야는 크게 (1) 자동 가설 생성 및 실험 설계, (2) 자동 논문 작성 및 피어 리뷰, (3) 과학적 발견을 위한 LLM 에이전트, (4) 도메인 특화 AI (단백질 구조 예측, 수학 증명 등)로 나뉜다. AI4Science는 2020년대 초반부터 성장해왔으나, LLM 기반 자동화 연구는 2023~2024년에 급증했다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE 'AI scientist 분야를 탐색한 적이 있다%';

-- 노드 2: Sakana AI — NeurIPS 오류 수정 (가장 중요)
UPDATE memory_nodes
SET content = 'Sakana AI의 "The AI Scientist" (2024년 8월 arXiv 프리프린트)가 이 분야의 대표적 연구다. 연구 아이디어 생성부터 실험 실행, 논문 작성, 자동 피어 리뷰까지 전 과정을 자동화하는 시스템을 제안했다. 발표 후 큰 주목을 받았으나 동시에 논란도 있었다. 후속작 AI Scientist-v2(2025)에서 ICLR 2025 워크숍에 AI 생성 논문 1편이 피어 리뷰를 통과한 것이 최초 사례로 기록되었다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE '%Sakana AI%';

-- 노드 3: FunSearch — Nature 게재, 성과 추가
UPDATE memory_nodes
SET content = 'DeepMind의 FunSearch (2023, Nature 게재)는 LLM과 진화적 탐색을 결합하여 새로운 수학적 발견을 한 사례다. 조합론의 cap set 문제에서 8차원 기준 기존 최고 기록(496)을 512로 경신하여 20년 만의 최대 개선을 달성했다. bin-packing 문제에서도 기존 휴리스틱을 능가하는 해를 찾았다. LLM이 코드를 생성하고 평가 함수가 자동 검증하는 자기 개선 루프 구조였다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE '%FunSearch%';

-- 노드 4: ChemCrow — 정식 출판, 성과 추가
UPDATE memory_nodes
SET content = 'ChemCrow (2023 arXiv, 2024 Nature Machine Intelligence 정식 출판)는 화학 분야에서 GPT-4 기반 LLM 에이전트가 18개 전문 도구를 사용하여 분자 설계, 합성 경로 탐색, 약물 탐색 등을 수행하는 시스템이다. 방충제 합성, 유기촉매 3종 합성 계획, 신규 발색단 발견 가이드 등의 성과를 보였다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE '%ChemCrow%';

-- 노드 5: Novelty 검증 — truthfulness, ICLR 2025 결과 추가
UPDATE memory_nodes
SET content = '자동 가설 생성 연구에서 핵심 쟁점은 novelty 검증과 truthfulness이다. LLM이 생성한 가설이 정말 새로운 것인지, 기존 연구의 재조합인지 판단하기 어렵다. ICLR 2025 연구(100+ NLP 연구자 참여)에 따르면 LLM 생성 아이디어는 인간 전문가보다 novelty는 높지만 실현 가능성(feasibility)은 낮은 경향이 있다. 문헌 검색 및 지식 그래프 기반 novelty/truthfulness check 방법이 제안되고 있다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE '%자동 가설 생성%';

-- 노드 6: 자동 리뷰 — 수치 오류 수정 (중요)
UPDATE memory_nodes
SET content = '자동 논문 리뷰 연구에서 GPT-4와 인간 리뷰어의 내용 겹침률은 약 30~39% 수준으로, 인간 리뷰어 간 겹침률(29~35%)과 비슷한 범위다. 다만 LLM은 점수를 인간보다 관대하게 매기는 경향이 있다. 전문가를 대체하기는 어렵지만, 초기 스크리닝이나 형식 검토에는 활용 가능성이 있다. ICLR 2024에서 리뷰의 약 15.8%가 LLM 보조를 받은 것으로 추정되어 학계에서 AI 리뷰 윤리 논의가 활발하다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE '%자동 논문 리뷰%';

-- 노드 7: 공통적 한계 — 검증 결과 정확, 수정 없음

-- 노드 8: 용어 다양성 — 최신 용어 추가
UPDATE memory_nodes
SET content = 'AI scientist 분야는 다양한 이름으로 불린다. "automated scientific discovery", "AI for science (AI4Science)", "LLM-driven research", "autonomous research agent", "AI co-scientist", "agentic AI for science" 등이 비슷한 맥락에서 사용된다. 최근에는 "Artificial Research Intelligence (ARI)"라는 용어도 등장했다. 검색 시 용어 변이에 주의해야 한다.'
WHERE context_hint = 'AI scientist 연구 경험'
  AND content LIKE '%다양한 이름으로 불린다%';

-- 추가 노드 3건 (2024~2025 주요 발전)
INSERT INTO memory_nodes (user_id, conversation_id, content, node_type, context_hint, is_hub)
VALUES
('00000000-0000-0000-0000-000000000000', null,
 'DeepMind의 AlphaFold 개발자 Demis Hassabis와 John Jumper가 2024년 노벨 화학상을 수상했다. AI가 과학적 발견에 기여한 것이 최고 권위의 학술상으로 인정받은 최초의 사례다. AlphaFold2는 190개국 200만 명 이상이 사용했으며, 2024년 발표된 AlphaFold3는 단백질뿐 아니라 DNA, RNA, 리간드와의 복합체 구조 예측까지 확장했다.',
 'fact', 'AI scientist 연구 경험', false),

('00000000-0000-0000-0000-000000000000', null,
 'Google DeepMind이 2025년 발표한 AI co-scientist는 Gemini 2.0 기반 멀티 에이전트 시스템으로, 과학자의 가설 생성과 연구 제안을 돕는 가상 협력자다. 급성 골수성 백혈병 약물 재활용 후보를 제안하여 실험실에서 검증에 성공했고, 간 섬유화 치료를 위한 새로운 후성유전 타겟도 제안하여 인간 간 오가노이드에서 효과가 확인되었다.',
 'fact', 'AI scientist 연구 경험', false),

('00000000-0000-0000-0000-000000000000', null,
 'FutureHouse(Eric Schmidt 후원)는 2025년 멀티 에이전트 시스템 Robin을 통해 건성 황반변성(dAMD) 치료 후보 물질을 발견하고, 인간 연구자가 2.5개월 만에 실험실 검증에 성공했다. 문헌 검색, 데이터 분석, 합성 설계 등 특화 에이전트를 조합한 lab-in-the-loop 프레임워크가 핵심이다.',
 'fact', 'AI scientist 연구 경험', false);
```

### 2. 임베딩 재계산

마이그레이션 적용 후:

```bash
npx tsx scripts/seed-embeddings.ts
```

UPDATE된 노드는 content가 변경되었으므로 임베딩을 재계산해야 한다. seed-embeddings.ts가 임베딩이 없거나 content가 변경된 노드를 처리하는지 확인 필요. 처리하지 않으면 해당 노드의 embedding 컬럼을 null로 리셋한 후 실행:

```sql
-- UPDATE된 노드의 임베딩 리셋 (seed-embeddings.ts가 null만 처리하는 경우)
UPDATE memory_nodes SET embedding = null
WHERE context_hint = 'AI scientist 연구 경험';
```

## 참조 파일

| 파일 | 역할 |
|------|------|
| `supabase/migrations/00010_ai_scientist_seed_nodes.sql` | 기존 시드 노드 (이번에 수정 대상) |
| `scripts/seed-embeddings.ts` | 임베딩 계산 + 네트워크 재구축 |

## 완료 기준

- [ ] 8개 기존 노드의 content가 검증된 내용으로 UPDATE됨
- [ ] 3개 신규 노드가 INSERT됨 (AlphaFold 노벨상, Google AI co-scientist, FutureHouse Robin)
- [ ] 임베딩 재계산 + 네트워크 연결 완료
- [ ] "AI scientist" 관련 대화 시 정확한 정보가 활성화됨
