# 프로젝트 목록

## [x] Agentic Engineering 방법론 (1차)
- 목표: AI 에이전트 시대의 협업, 개발, 서비스 설계 방법론 수립
- 도메인: 개발, 리서치
- 완료:
  - [x] 프로젝트 구조 세팅 (collaboration / development / service-design)
  - [x] AI-인간 협업 체계 정리
  - [x] 기술적 결 — 개발 방법론 도출
  - [x] AI 서비스 설계 원칙 수립 (mirror-mind 철학 반영)
  - [x] 안전장치·지식 공급·관측 체계 원칙 추가
- 향후 과제:
  - [ ] 실제 프로젝트 적용을 통한 방법론 검증 및 개선
  - [ ] 모니터링·디버깅 시스템 구현 가이드라인 실전 적용
  - [ ] 도메인별 원칙 문서 확장 (development-principle.md, research-principle.md)

## [>] Light House — 연구 동료 에이전트 서비스
- 목표: 학술 논문 검색 + AI 분석 연구 탐색 도구. mirror-mind 철학을 서비스에 적용
- 도메인: 서비스 설계, 개발
- 저장소: `/Users/jaeyoungkang/corca/lighthouse/`
- 원칙 원본: `projects/lighthouse/service-principles.md`
- 하위 업무:
  - [x] 문서 얼라인 — 대원칙 수립 + 하위 문서 정렬
    - [x] 대원칙 초안 작성 (service-principles.md)
    - [x] lighthouse docs/ 문서 정렬 (ai-design-framework 리네이밍, 대원칙 참조 추가, 3-Plane/관측 보강)
    - [x] mirror-mind 방법론 역수입 (체크리스트, FSM 패턴, 정합성 문서 패턴, 문서 계층 패턴)
  - [ ] 관측 체계 설계 문서 작성
  - [ ] 실전 운영 후 방법론 검증 및 개선

## [>] 메타에이전트 — 원칙 준수 감시
- 목표: 대화 중 mirror-mind-principle.md, task-management-principle.md 등의 원칙이 지켜지고 있는지 상시 점검
- 도메인: 운영
- 하위 업무:
  - [x] 프로토타입 구현 (세션 중 JSONL 실시간 읽기 + 원칙 위반 감지)
  - [x] 세션 시작 절차에 통합 (AGENTS.md, 5분 간격)
  - [ ] 실전 운영 후 점검 항목 개선
