# Mirror Mind — 네비게이션

이 저장소의 모든 작업에서 `mirror-mind-principle.md`를 단일 원본(single source of truth)으로 사용한다.

---

## 문서 맵

| 문서 | 역할 |
|------|------|
| `mirror-mind-principle.md` | 최상위 철학 — Co-actor 4대 원칙, 소통 규범 |
| `agentic-engineering-principles.md` | 설계 + 개발 원칙 — 자율성, 안전, 관계 형성, 기술적 결, 관측 |
| `operations.md` | 운영 — 업무 관리, 세션 절차, 기억 시스템, 메타에이전트 |
| `tasks/projects.md` | 프로젝트 현황 — 업무 목록, 진행 상태, 일정 |

## 프로젝트별 설계 문서

| 프로젝트 | 문서 |
|---------|------|
| Light House | `projects/lighthouse/service-principles.md` — 서비스 원칙 |
| | `projects/lighthouse/research-scenarios.md` — 연구자 행동 시나리오 |
| | `projects/lighthouse/user-memory-concept.md` — 사용자 기억 설계 |
| Moonlight | `projects/moonlight/university-event.md` — 대학 이벤트 |

## 기억 네트워크

| 파일 | 역할 |
|------|------|
| `memory/network/nodes.json` | fact/intention 노드 |
| `memory/network/embeddings.json` | 벡터 |
| `memory/network/graph.json` | knn_k12 엣지 |
| `scripts/activate.py` | spreading activation |
| `memory/experiment-report.md` | v3 실험 기록 |

## 트리거 (빠른 참조)

| 키워드 | 동작 |
|--------|------|
| **작업 시작** | `operations.md` 세션 시작 절차 |
| **작업 종료** | `operations.md` 세션 종료 절차 |
| **주제 전환** / **킵** | 중간 상태 기록 → 전환 |
| **정합성 검증** | 전체 문서 상호 참조 검증 |
| **회고** | 마일스톤 회고 + 원칙 반영 |
| **원칙 점검** | 메타에이전트 1회 실행 |
