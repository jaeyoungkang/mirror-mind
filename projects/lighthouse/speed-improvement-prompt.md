# 속도 개선 구현 프롬프트

> 시연 전 최우선 작업. 두 가지 독립적인 개선.

## 1. 논문 분석 병렬화

`app/server/tools/analyze-papers.ts`에서 논문 분석이 `for` 루프로 순차 실행되고 있다.
5편 분석 시 순차로 5~10초 걸리는 것을 병렬로 바꿔 1~2초로 줄인다.

### 변경 대상

`app/server/tools/analyze-papers.ts` L48~96의 `execute` 함수

### 변경 내용

```
기존:
  for (const paper of papers) {
    const analysis = await executeJudgment(...)
    const artifact = await createArtifact(...)
    results.push(...)
  }

변경 후:
  const settled = await Promise.allSettled(
    papers
      .filter(p => p.abstract)
      .map(async (paper) => {
        const analysis = await executeJudgment(...)
        if (!analysis) return null
        const artifact = await createArtifact(...)
        return { paperId, title, artifactId }
      })
  )
  results = settled
    .filter(r => r.status === 'fulfilled' && r.value !== null)
    .map(r => r.value)
```

### 주의사항

- `Promise.allSettled`을 사용하여 일부 실패해도 나머지 결과를 반환한다
- Gemini API rate limit 고려: 동시 요청이 20편을 넘지 않도록 한다 (현재 기본 limit=20이므로 문제없음)
- `createArtifact`는 각각 독립적인 DB insert이므로 병렬 실행에 안전하다

## 2. 검색 자동 실행 제어

현재 시스템 프롬프트에서 "사용자가 명시적으로 검색을 요청했을 때"는 propose 없이 바로 search_papers를 실행하도록 되어 있다. 문제: LLM이 "명시적 요청"을 너무 넓게 해석하여 사용자가 주제만 언급해도 검색으로 직행한다.

### 변경 대상

`app/server/agent/system-prompt.ts` L74 부근

### 현재

```
**예외**: 사용자가 명시적으로 검색을 요청했을 때(예: "transformer 논문 찾아줘")는 propose 없이 바로 search_papers를 실행한다. 이 경우 사용자의 의도가 명확하므로 L5처럼 행동한다.
```

### 변경 후

```
**예외**: 사용자가 "찾아줘", "검색해줘", "논문 있나?" 같은 직접적인 검색 동사를 사용했을 때만 propose 없이 search_papers를 실행한다. 다음은 명시적 요청이 **아니다**:
- 주제를 언급만 한 경우 ("AI scientist에 대해 관심이 있어요")
- 질문을 한 경우 ("이 분야에 어떤 연구가 있나요?")
- 방향을 논의하는 경우 ("이쪽으로 더 깊이 들어가볼까")
이런 경우에는 반드시 propose를 통해 검색을 제안한다. 검색 전에 사용자의 의도를 충분히 파악하는 것이 우선이다.
```

## 참조 파일

| 파일 | 역할 |
|------|------|
| `app/server/tools/analyze-papers.ts` | 논문 분석 도구 (병렬화 대상) |
| `app/lib/llm-judgment.ts` | executeJudgment 공통 LLM 호출 |
| `app/server/agent/system-prompt.ts` | 시스템 프롬프트 (검색 제어 대상) |

## 완료 기준

- [ ] analyze_papers가 5편을 병렬로 분석하여 2초 이내 완료
- [ ] 주제 언급만으로 검색이 자동 실행되지 않음 (propose를 통해 제안)
- [ ] 기존 테스트/기능에 영향 없음
