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
4. `tasks/decisions.md`의 최근 항목을 읽고 맥락을 복원한다
5. 메타에이전트를 백그라운드로 실행한다: `python meta-agent/scripts/check.py --watch --interval 300`
6. 사용자에게 현재 상태를 요약하고 다음 작업을 제안한다 (메타에이전트 초기 리포트 포함)

---

## 트리거 지시문

사용자가 아래 키워드를 사용하면 해당 절차를 수행한다.

| 트리거 | 절차 |
|--------|------|
| **작업 시작** | 위 세션 시작 절차 수행 |
| **작업 종료** | 대화 노트 작성(`tasks/conversations/`), raw 저장(`tasks/conversations/raw/`), `tasks/decisions.md` 업데이트, 커밋 |
| **주제 전환** / **킵** | 현재 주제의 중간 상태를 `tasks/projects.md`(결정 전) 또는 `tasks/decisions.md`(결정 후)에 기록한 뒤 전환 |
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

## 점진적 확장 TODO

프로젝트 진행 중 새로운 도메인이 등장하면 해당 도메인의 원칙 문서를 생성한다.
각 문서는 해당 도메인 전문 에이전트가 참조하는 기준이 된다.

- [x] `task-management-principle.md` — 업무 관리 에이전트용
- [ ] 예: `development-principle.md` — 개발 에이전트용
- [ ] 예: `research-principle.md` — 리서치 에이전트용
