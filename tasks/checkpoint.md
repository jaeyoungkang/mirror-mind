# 체크포인트 — 세션46

## 진행 상태

### 1. Collection 문서 타입 도입 (핵심)
- "폴더도 문서다" 철학 논의 → 합의
- 구현 프롬프트 작성 완료: `projects/lighthouse/collection-document-prompt.md`
- 재영이 구현 에이전트에 전달함
- Phase 0~5 단계별 설계 (Domain → DB → Repository → API → 클라이언트 → 도구 연동)
- 핵심 결정: conversations 테이블 유지, collection 생성 시 대응 conversation 동시 생성, childIds와 refs 분리

### 2. lighthouse 설계 문서 정리
- mirror-mind `projects/lighthouse/` 9개 문서 + lighthouse `docs/` 8개 문서 교차 분석 완료
- **제거 3건**: shared-tools-design.md, tile-workspace-prompt.md, scroll-strip-prompt.md
- **수정 1건**: document-architecture.md — lighthouse 최신 버전으로 동기화 + collection 반영
- **유지 5건**: service-principles.md, research-scenarios.md, user-memory-concept.md, 초기대화흐름.md, collection-document-prompt.md
- AGENTS.md 문서 맵은 이미 정확 (삭제한 문서는 등록되어 있지 않았음)

## 핵심 맥락

- .prompt 파일에 미반영 피드백 다수 존재 (검색 경험 개선, 최초 대화, 재방문 흐름, 툴 사용 경험, 세션-문서 종속, 기억 aging 등)
- Lighthouse 핵심 경험 1차 (A/B/C) 다듬기 중 — 검색 이슈 디버깅 필요
- Moonlight 사용설명서 로컬 테스트 + 프로덕션 배포 남음 (마감 3/13)

## 다음 할 일

1. tasks/projects.md 업데이트 — collection 문서 업무 등록, 문서 정리 완료 반영
2. .prompt 메모 → tasks/projects.md 구조화 (미반영 피드백 업무 등록)
3. Lighthouse 핵심 경험 1차 마무리 (검색 이슈)
4. Moonlight 배포
