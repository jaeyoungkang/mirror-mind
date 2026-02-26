# Mirror Mind Collaboration Rule

이 저장소의 모든 작업에서 `mirror-mind-principle.md`를 단일 원본(single source of truth)으로 사용한다.

1. 모든 턴 시작 시 `mirror-mind-principle.md`를 먼저 읽고 적용한다.
2. 협업 원칙/행동 규범은 `AGENTS.md`에 복사하지 않는다.
3. 원칙 수정은 `mirror-mind-principle.md`에서만 수행한다.

---

## 세션 시작 절차
1. `mirror-mind-principle.md`를 읽고 협력 원칙을 적용한다
2. `task-management-principle.md`를 읽고 업무 관리 방식을 파악한다
3. `tasks/projects.md`를 읽고 현재 진행 상태를 파악한다
4. 기억 네트워크로 맥락을 보강한다:
   - `memory/.venv/bin/python3 memory/scripts/activate.py --query "현재 주제"` — 네트워크 spreading activation으로 관련 기억 활성화
   - 주제 전환 시에도 새 주제로 기억을 활성화한다
5. 메타에이전트를 백그라운드로 실행한다: `python meta-agent/scripts/check.py --watch --interval 300`
6. 사용자에게 현재 상태를 요약하고 다음 작업을 제안한다 (메타에이전트 초기 리포트 + 기억 요약 포함)

---

## 트리거 지시문

사용자가 아래 키워드를 사용하면 해당 절차를 수행한다.

| 트리거 | 절차 |
|--------|------|
| **작업 시작** | 위 세션 시작 절차 수행 |
| **작업 종료** | 메타에이전트 리포트 확인 → `python3 scripts/close-session.py` 실행 (raw 저장 + 노드 추출 + 네트워크 갱신) → 초안 검토·수정 → `tasks/projects.md` 수동 업데이트 → 커밋 |
| **주제 전환** / **킵** | 메타에이전트 리포트 확인 → 현재 주제의 중간 상태를 `tasks/projects.md`에 기록한 뒤 전환 |
| **정합성 검증** | 전체 원칙·설계 문서를 읽고 상호 참조·일관성을 검증하여 리포트 |
| **회고** | 마일스톤 단위 회고 진행, 반복 적용할 교훈을 해당 원칙 문서에 반영 |
| **원칙 점검** | `python meta-agent/scripts/check.py` 1회 실행, 위반 사항 리포트 |

---

## 도메인별 원칙 문서
- `task-management-principle.md` — 업무 관리 원칙
- `agentic-engineering/development/technical-grain.md` — 기술적 결 (개발 방법론)
- `agentic-engineering/service-design/ai-service-design-principles.md` — AI 서비스 설계 원칙
- `meta-agent/meta-agent-principle.md` — 메타에이전트 (원칙 준수 감시)

---

## 기억 시스템 (v3 네트워크)
- `memory/network/nodes.json` — fact/intention 노드 (knn_k12 네트워크)
- `memory/network/embeddings.json` — OpenAI text-embedding-3-small 벡터
- `memory/network/graph.json` — knn_k12 엣지
- `memory/scripts/activate.py` — spreading activation 기반 기억 활성화
- 세션 시작 시 activate.py로 맥락 활성화, 주제 전환 시 재활성화
- 세션 종료 시 close-session.py가 노드 추출 + 네트워크 갱신 자동 수행

---

## 점진적 확장 TODO

프로젝트 진행 중 새로운 도메인이 등장하면 해당 도메인의 원칙 문서를 생성한다.
각 문서는 해당 도메인 전문 에이전트가 참조하는 기준이 된다.

- [x] `task-management-principle.md` — 업무 관리 에이전트용
- [ ] 예: `development-principle.md` — 개발 에이전트용
- [ ] 예: `research-principle.md` — 리서치 에이전트용
