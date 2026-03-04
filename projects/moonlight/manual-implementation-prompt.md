# 나의 학기 사용설명서 — 구현 프롬프트

기존 캠퍼스 액티비티(학업 운세)를 **"나의 학기 사용설명서"** 5챕터 시스템으로 전면 교체한다.

---

## 1. 콘셉트

- 이름: **나의 학기 사용설명서**
- MBTI 기반, 매일 1챕터씩 언락 (5일 완성)
- 각 챕터는 서로 다른 포맷의 카드를 생성
- 인앱 카드에는 MBTI 미표시, 공유 카드(OG)에만 MBTI 표시
- 참여 = 응원 +1, 공유 유입 = 공유자 응원 +1 (기존과 동일)

### 5개 챕터

| CH | 이름 | 핵심 | 감정 트리거 |
|----|------|------|------------|
| 1 | 이번 학기 생존 확률 | 큰 숫자 + 게이지바 | 긴장/비교 ("너 몇 %?") |
| 2 | 나의 학기 스탯 | RPG 스탯바 5개 + 칭호 | 자기표현/비교 |
| 3 | 새학기 금지어 | 금지어 3개 + 대안 | 찔림/웃김 |
| 4 | 이번 학기 시나리오 | 3~6월 타임라인 서사 | 공감/웃픔 |
| 5 | 교수님 궁합 (대학원: 지도교수님) | 교수 유형 + 별점 + 생존전략 | 공감/재미 |

---

## 2. 입력

| 항목 | 필수 | 비고 |
|------|------|------|
| MBTI | 필수 | 4글자, 기존과 동일 |
| 대학 | 자동 | 이메일 도메인에서 `detectUniversity()` |
| 전공 | 선택 | 자유 텍스트 |
| 학년 | 선택 | 드롭다운 (아래 참조) |

### 학년 옵션 변경

기존 `['1학년', '2학년', '3학년', '4학년', '대학원생']`을 세분화:

```typescript
const GRADE_OPTIONS = [
  '1학년', '2학년', '3학년', '4학년',  // 학부
  '석사', '박사',                       // 대학원
];
```

학년에 따라 LLM 프롬프트의 맥락이 크게 달라진다:
- **학부 저학년** (1~2학년): 수강신청, OT, 동아리, 새 친구, 교양 수업
- **학부 고학년** (3~4학년): 전공심화, 취업 준비, 졸업 요건, 인턴
- **대학원** (석사/박사): 랩미팅, 논문, 지도교수, 학회 마감, 졸업 압박, 연구실 생활

---

## 3. 언락 규칙

### 첫 참여일 기준 순차 해금

```
CH.1: D+0 (첫 참여일)
CH.2: D+1
CH.3: D+2
CH.4: D+3
CH.5: D+4
```

- 기준 시각: KST 자정 (`getTodayKST()`)
- "첫 참여일" = 해당 유저의 `campus_activity_results`에서 `activity_type LIKE 'manual-%'`인 최초 레코드의 `date`
- 첫 참여일이 없으면 오늘이 D+0 (CH.1만 열림)
- D+4 이후: 5개 모두 열림

### 매일 새 결과

- 같은 챕터도 날짜가 바뀌면 새 결과 생성 가능
- 기존 UNIQUE 제약 `(user_id, date, activity_type)` 그대로 활용
- 하루에 열린 챕터 중 1개만 생성 가능 (응원 +1 하루 1회 유지)

> **하루 1개 제한 이유**: 5개 전부 하면 하루에 응원 +5가 되어 밸런스 붕괴. 하루 1챕터 = 응원 +1 = 5일 연속 참여 인센티브.

### progress 조회 API

```
GET /api/campus-activity/manual/progress
```

응답:
```typescript
{
  firstDate: string | null;        // 첫 참여일 (YYYY-MM-DD)
  chapters: {
    ch: number;                    // 1~5
    name: string;
    unlocked: boolean;             // 오늘 기준 해금 여부
    completedToday: boolean;       // 오늘 이미 생성했는지
    lastResult: object | null;     // 가장 최근 결과 (표시용)
  }[];
  completedTodayCount: number;     // 오늘 생성한 챕터 수 (0 or 1)
  totalCompleted: number;          // 지금까지 생성한 고유 챕터 수 (0~5)
}
```

---

## 4. DB 변경

### 기존 테이블 활용

`campus_activity_results` 테이블을 그대로 사용한다. 변경 없음.

- `activity_type`: `'manual-ch1'` ~ `'manual-ch5'`
- `input`: `{ mbti, major, grade, university }` (JSON)
- `result`: 챕터별 LLM 결과 (JSON, 챕터마다 스키마 다름)
- UNIQUE `(user_id, date, activity_type)`: 하루 1회 제한 자동 적용

### 하루 1개 제한 로직

generate 엔드포인트에서 추가 체크:
```sql
SELECT COUNT(*) FROM campus_activity_results
WHERE user_id = $1 AND date = $2 AND activity_type LIKE 'manual-%'
```
count > 0이면 409 반환 (오늘 이미 다른 챕터를 생성함).

---

## 5. 서버 구현

### 5.1 Activity 등록

기존 레지스트리 패턴을 따라 5개 활동을 등록한다.

**파일**: `packages/moonlight-server/src/campus-activity/activities/manual.ts`

하나의 파일에서 5개 활동을 정의하고 export. 공통 로직은 함수로 추출.

```typescript
// manual.ts
import { registerActivity } from '../registry';

// 공통 입력 스키마 (기존 fortune과 동일)
const manualInputSchema = z.object({
  mbti: z.string().length(4).regex(/^[EI][SN][TF][JP]$/i),
  major: z.string().max(100).optional(),
  grade: z.string().max(50).optional(),
});

// 챕터별 결과 스키마 + 프롬프트 + 등록
registerManualChapter(1, 'manual-ch1', ch1ResultSchema, ch1SystemPrompt, buildCh1Prompt);
registerManualChapter(2, 'manual-ch2', ch2ResultSchema, ch2SystemPrompt, buildCh2Prompt);
// ... ch3, ch4, ch5
```

### 5.2 LLM 설정

```typescript
model: AIModel.GEMINI_3_FLASH    // gemini-3-flash-preview
temperature: 0.95                 // 높은 다양성
responseFormat: { type: 'json_object' }
```

### 5.3 챕터별 결과 스키마 + 프롬프트

#### 공통 시스템 프롬프트 프레임

모든 챕터가 공유하는 기본 지침:

```
당신은 대학생을 위한 MBTI 콘텐츠 작가입니다. "나의 학기 사용설명서" 시리즈를 작성합니다.

## 핵심 원칙
1. "아 이거 나야ㅋㅋ" 하고 찔리는 수준의 구체성
2. 대학생 일상의 디테일 (수강신청, 도서관, 학식, 조별과제, 동아리, 축제 등)
3. MBTI 특성이 학업 상황에서 어떻게 드러나는지 구체적으로
4. 톤: 친한 친구가 장난치듯 직설적이고 웃기게. 존댓말 금지.
5. 새학기 분위기 (설렘 + 긴장 + 다짐)

## 맥락 분기
- 학부 저학년(1~2학년): 수강신청, OT, 동아리, 새 친구, 교양, 대학 적응
- 학부 고학년(3~4학년): 전공심화, 취업, 졸업요건, 인턴, 학점 관리
- 석사: 랩미팅, 논문, 지도교수, 학회, 연구실, 코딩/실험, 졸업 압박
- 박사: 연구 독립성, 디펜스, 퍼블리케이션, 번아웃, 학계 커리어

## 대학 맥락
대학 이름이 주어지면 해당 대학의 캠퍼스, 문화, 별명, 랜드마크를 자연스럽게 녹여라.
모르는 대학이면 일반적인 대학 맥락을 사용하되, 대학 이름은 언급하라.

## 전공 맥락
전공이 주어지면 해당 전공 특유의 학업 상황, 과목, 고충을 반영하라.
전공이 없으면 일반적인 대학 맥락을 사용하라.

## 다양성
같은 MBTI라도 날짜에 따라 완전히 다른 결과를 생성하라.
매번 새로운 비유, 상황, 표현을 사용하라. 반복 금지.

반드시 지정된 JSON 형식으로만 응답하세요.
```

#### CH.1 이번 학기 생존 확률

**결과 스키마:**
```typescript
const ch1ResultSchema = z.object({
  survival_rate: z.number().min(30).max(95),
  title: z.string(),           // 한 줄 요약 (15자 이내 권장)
  strength: z.string(),        // 강점 (25자 이내)
  danger: z.string(),          // 위험 (25자 이내)
  survival_tip: z.string(),    // 생존팁 (25자 이내)
  comment: z.string(),         // 마무리 코멘트 (30자 이내)
});
```

**프롬프트 빌더:**
```
[CH.1 이번 학기 생존 확률]

정보: MBTI={mbti}, 대학={university}, 전공={major}, 학년={grade}, 날짜={date}

생존 확률(30~95%)을 MBTI 특성에 맞게 설정하라.
- 강점/위험/팁은 이 사람의 구체적인 학업 상황에서 뽑아라
- title은 카드 중앙에 크게 들어가는 문구. 짧고 임팩트 있게.
- comment는 카드 하단의 한마디. 웃기거나 찔리게.
- 모든 텍스트는 짧게. 카드에 들어가야 한다.

{JSON 스키마}
```

#### CH.2 나의 학기 스탯

**결과 스키마:**
```typescript
const ch2ResultSchema = z.object({
  stats: z.array(z.object({
    name: z.string(),
    value: z.number().min(10).max(99),
  })).length(5),
  badge: z.string(),           // 칭호 (10자 이내)
  description: z.string(),     // 한 줄 설명 (30자 이내)
  hidden_stat: z.string(),     // 숨겨진 스탯 (이름+값, 20자 이내)
});
```

**프롬프트 빌더:**
```
[CH.2 나의 학기 스탯]

정보: MBTI={mbti}, 대학={university}, 전공={major}, 학년={grade}, 날짜={date}

RPG 캐릭터 시트를 만들어라.

스탯 5개:
- 학부생: 학점력 / 인싸력 / 과제력 / 벼락치기 / 멘탈
- 대학원생: 학점력 / 인싸력 / 논문력 / 데드라인 서바이벌 / 멘탈

규칙:
- value는 10~99. MBTI 특성이 스탯에 명확히 드러나야 한다.
- badge(칭호)는 RPG 칭호처럼 웃기고 핵심을 찌르는 이름. 대학/전공 맥락 반영.
- hidden_stat은 "OO력 99" 형태. 예상 못한 능력.
- description은 이 캐릭터를 한 줄로 요약. 찔리거나 웃기게.

{JSON 스키마}
```

#### CH.3 새학기 금지어

**결과 스키마:**
```typescript
const ch3ResultSchema = z.object({
  forbidden: z.array(z.object({
    phrase: z.string(),        // 금지어 (20자 이내)
    roast: z.string(),         // 디스 (25자 이내)
  })).length(3),
  instead: z.string(),         // 대안 (25자 이내)
  comment: z.string(),         // 마무리 (25자 이내)
});
```

**프롬프트 빌더:**
```
[CH.3 새학기 금지어]

정보: MBTI={mbti}, 대학={university}, 전공={major}, 학년={grade}, 날짜={date}

이번 학기에 하면 안 되는 말 3가지를 만들어라.

규칙:
- 매학기 습관처럼 하는 말인데 결국 후회하는 것들
- MBTI 특성 + 학년 맥락에서 나오는 금지어 (학부생과 대학원생은 완전히 다르다)
- roast는 친구가 "야 너 또 그러냐" 하는 느낌. 짧고 날카롭게.
- instead는 현실적이고 웃긴 대안
- 모든 텍스트는 카드에 들어갈 수 있게 짧게

{JSON 스키마}
```

#### CH.4 이번 학기 시나리오

**결과 스키마:**
```typescript
const ch4ResultSchema = z.object({
  episodes: z.array(z.object({
    month: z.string(),         // "3월", "4월", "5월", "6월"
    emoji: z.string(),
    title: z.string(),         // 짧은 제목 (10자 이내)
    description: z.string(),   // 상황 묘사 (30자 이내)
  })).length(4),
  ending: z.string(),          // 결말 (20자 이내)
  moral: z.string(),           // 교훈 (25자 이내)
});
```

**프롬프트 빌더:**
```
[CH.4 이번 학기 시나리오]

정보: MBTI={mbti}, 대학={university}, 전공={major}, 학년={grade}, 날짜={date}

3월~6월 4개 에피소드로 이번 학기를 시간순 서사로 풀어라.

규칙:
- MBTI 특성이 스토리에 녹아야 한다
- 학부생: 수업/시험/축제/동아리 중심의 서사
- 대학원생: 연구/논문/랩미팅/학회/지도교수 중심의 서사
- 각 에피소드는 해당 월의 실제 대학 이벤트와 연결 (3월 개강, 4월 중간, 5월 축제, 6월 기말)
- 대학원생은 학기 이벤트보다 연구 마일스톤 중심
- 결말과 교훈은 유머 있게
- 모든 텍스트 짧게

{JSON 스키마}
```

#### CH.5 교수님 궁합

**결과 스키마:**
```typescript
const ch5ResultSchema = z.object({
  prof_type: z.string(),             // 교수님 유형 (20자 이내)
  compatibility: z.number().min(1).max(5),
  compatibility_label: z.string(),   // 궁합 한 줄 (15자 이내)
  danger_point: z.string(),          // 위험 + 확률% (25자 이내)
  survival_strategy: z.string(),     // 생존 전략 (40자 이내)
  one_liner: z.string(),             // 교수님 한마디 (30자 이내)
});
```

**프롬프트 빌더:**
```
[CH.5 교수님 궁합]

정보: MBTI={mbti}, 대학={university}, 전공={major}, 학년={grade}, 날짜={date}

가상의 교수님 유형을 생성하고 MBTI와의 궁합을 보라.

규칙:
- 학부생: "교수님" — 수업 교수님 유형 (출석체크형, 조별과제형, 교재 직접 쓴 형 등)
- 대학원생: "지도교수님" — 연구 지도 유형 (새벽 슬랙형, 방목형, 완벽주의형 등)
- 교수님 유형은 대학생/대학원생이 보편적으로 공감하는 유형 중 하나
- 위험 포인트의 확률%는 과장해서 웃기게 (예: 142.8%)
- one_liner는 교수님 시점에서 이 학생을 한마디로. 이게 제일 재밌어야 한다.
- 전공이 있으면 해당 전공 교수님 맥락

{JSON 스키마}
```

### 5.4 라우터 확장

기존 `router.ts`에 progress 엔드포인트 추가:

```typescript
// GET /campus-activity/manual/progress
router.get('/manual/progress', authMiddleware, async (req, res) => {
  const userId = req.user.id;
  const today = getTodayKST();

  // 1. 이 유저의 manual-* 최초 참여일 조회
  const firstResult = await db.query(`
    SELECT MIN(date) as first_date
    FROM campus_activity_results
    WHERE user_id = $1 AND activity_type LIKE 'manual-%'
  `, [userId]);

  const firstDate = firstResult.rows[0]?.first_date || null;

  // 2. 오늘 기준 해금 챕터 계산
  const daysSinceFirst = firstDate
    ? Math.floor((new Date(today) - new Date(firstDate)) / 86400000)
    : 0;

  // 3. 오늘 생성한 챕터 조회
  const todayResults = await db.query(`
    SELECT activity_type, result
    FROM campus_activity_results
    WHERE user_id = $1 AND date = $2 AND activity_type LIKE 'manual-%'
  `, [userId, today]);

  // 4. 각 챕터의 가장 최근 결과 조회
  const lastResults = await db.query(`
    SELECT DISTINCT ON (activity_type) activity_type, result, date
    FROM campus_activity_results
    WHERE user_id = $1 AND activity_type LIKE 'manual-%'
    ORDER BY activity_type, date DESC
  `, [userId]);

  // 5. 응답 구성
  // ...
});
```

### 5.5 generate 엔드포인트 하루 1챕터 제한

기존 `router.ts`의 `POST /:activityType/generate`에 manual 전용 체크 추가:

```typescript
// manual 활동이면 오늘 다른 manual 챕터 생성 여부 체크
if (activityType.startsWith('manual-')) {
  const todayManualCount = await db.query(`
    SELECT COUNT(*) FROM campus_activity_results
    WHERE user_id = $1 AND date = $2 AND activity_type LIKE 'manual-%'
  `, [userId, today]);

  if (parseInt(todayManualCount.rows[0].count) > 0) {
    return res.status(409).json({
      error: 'DAILY_MANUAL_LIMIT',
      message: '오늘은 이미 다른 챕터를 완료했습니다. 내일 다시 도전하세요!'
    });
  }

  // 언락 체크
  const chapterNum = parseInt(activityType.replace('manual-ch', ''));
  // firstDate 조회 후 daysSinceFirst 계산
  if (daysSinceFirst < chapterNum - 1) {
    return res.status(403).json({
      error: 'CHAPTER_LOCKED',
      message: `CH.${chapterNum}은 아직 잠겨있습니다.`
    });
  }
}
```

---

## 6. 프론트엔드 구현

### 6.1 컴포넌트 구조

기존 ActivitySection에서 FortuneCard 위치에 ManualCard를 대체 배치한다.

```
ActivitySection
├── ManualCard (360×580, 메인 위치)
│   ├── SelectionView (챕터 선택 화면)
│   │   ├── 타이틀 + 프로그레스바
│   │   ├── ChapterList (5개, 잠금/열림/완료 상태)
│   │   └── 하단 안내 텍스트
│   │
│   ├── InputView (MBTI 입력 — 첫 참여 시)
│   │   ├── MBTI 4차원 선택
│   │   ├── 전공 (선택)
│   │   ├── 학년 드롭다운 (선택)
│   │   └── 생성 버튼
│   │
│   └── ResultView (챕터별 결과)
│       ├── Ch1ResultCard (생존 확률)
│       ├── Ch2ResultCard (스탯)
│       ├── Ch3ResultCard (금지어)
│       ├── Ch4ResultCard (시나리오)
│       ├── Ch5ResultCard (교수님 궁합)
│       └── 공유 버튼 + 돌아가기 버튼
│
└── PlaceholderCard[] (나머지 슬롯)
```

### 6.2 SelectionView (챕터 선택 화면)

**디자인 참고**: `projects/moonlight/chapter-card-samples.html`의 선택 화면

```tsx
// 상태별 UI
// - 완료: ✅ + 챕터명 + "완료" (클릭 시 결과 보기)
// - 열림: 📊 + 챕터명 + "지금 확인하기" (보라색, 클릭 가능)
// - 잠금: 🔒 + 챕터명 + "내일 열림" / "D-N" (반투명)

// 프로그레스바: completedTotal / 5 비율
```

### 6.3 ResultView (챕터별 결과 렌더러)

각 챕터는 완전히 다른 레이아웃을 가진다. 5개의 별도 컴포넌트.

**공통 구조:**
```
┌────────────────────┐
│ CH.N    사용설명서  │  ← 상단 라벨
│ 챕터 제목           │  ← 큰 글씨
│ ─── accent ───     │
│                    │
│ (챕터별 콘텐츠)     │  ← 각각 다름
│                    │
├────────────────────┤
│ 대학·날짜   [공유]  │  ← 하단
└────────────────────┘
```

**카드 사이즈**: 360×580px (기존과 동일)

**챕터별 색상** (moonlight 톤 안에서):

| CH | 배경 그라데이션 | 액센트 |
|----|----------------|--------|
| 1 | `#0f0b2e → #1a1145` (기본 퍼플) | `#8b5cf6 → #c084fc` |
| 2 | `#0b1a2e → #112040` (블루) | `#605dec → #818cf8` |
| 3 | `#1a0b1a → #2d1228` (핑크) | `#ec4899 → #f472b6` |
| 4 | `#0b1a18 → #112e28` (그린) | `#34d399 → #2dd4bf` |
| 5 | `#1a130b → #2e2010` (오렌지) | `#fb923c → #f59e0b` |

**디자인 참고**: `projects/moonlight/chapter-card-samples.html`의 인앱 결과 카드

### 6.4 공유 버튼 동작

```typescript
const handleShare = (chapterResult) => {
  // 1. 공유 링크 생성 (기존 fortune_ref와 동일 패턴)
  const shareUrl = `https://www.themoonlight.io/ko/universities?fortune_ref=${userId}`;

  // 2. 클립보드 복사
  navigator.clipboard.writeText(shareUrl);

  // 3. 복사 완료 피드백
};
```

### 6.5 기존 FortuneCard 처리

기존 fortune 활동은 **유지하되 UI에서 숨긴다**. 기존 데이터가 있는 유저는 이전 결과에 접근 가능해야 한다. ActivitySection에서 fortune 대신 manual을 메인으로 표시.

---

## 7. OG 이미지

### 공유 카드 = OG 이미지 (MBTI 포함)

기존 `/api/og/campus-activity/route.tsx` 확장.

공유 카드는 인앱 카드와 다르게 **MBTI를 크게 표시**한다.

```
┌────────────────────┐
│ CH.N 생존확률  사용설명서 │
│ ENFP                │  ← MBTI 크게 (인앱에서는 숨김)
│ ─── accent ───     │
│ (챕터별 콘텐츠)      │
│                    │
│ 연세대·날짜  문라이트—나도해보기 │
└────────────────────┘
```

**구현**: 기존 `renderFortuneOg` 패턴을 따라 챕터별 OG 렌더 함수 추가.

```typescript
// ogRenderers Map에 5개 렌더러 등록
ogRenderers.set('manual-ch1', renderManualCh1Og);
ogRenderers.set('manual-ch2', renderManualCh2Og);
// ...
```

**디자인 참고**: `projects/moonlight/chapter-card-samples.html`의 공유용 카드

---

## 8. 응원 카운트

기존 로직 그대로:
- 챕터 생성 완료 시 → 본인 응원 +1 (GAS 연동, 기존 `addCheer`)
- 공유 링크 유입 → 공유자 응원 +1 (기존 `referral-cheer`)

변경 없음. 하루 1챕터 제한이 응원 밸런스를 자동으로 맞춘다.

---

## 9. 다양성 확보 전략

수만 명이 참여하므로 결과가 다양해야 한다. LLM 프롬프트만으로 다양성을 확보하는 전략:

### 9.1 입력 조합의 풍부함

- **MBTI 16종**: 각 성격 유형별 완전히 다른 결과
- **학년 6종**: 학부 저학년/고학년/대학원 석사/박사로 톤과 소재가 크게 분기
- **대학**: 대학별 캠퍼스 랜드마크, 문화, 별명 반영
- **전공**: 전공 특유의 과목, 고충, 용어 반영
- **날짜**: 매일 다른 시드 → 같은 입력이어도 다른 결과

### 9.2 프롬프트 설계

- **높은 temperature** (0.95): 최대 다양성
- **반복 금지 지시**: "매번 새로운 비유, 상황, 표현을 사용하라"
- **날짜 활용 지시**: "오늘 날짜를 시드로 활용하여 어제와 완전히 다른 결과를 만들어라"
- **구체성 요구**: "추상적 표현 금지. 구체적인 장소, 상황, 행동으로"

### 9.3 텍스트 길이 제한

카드에 표시해야 하므로 모든 텍스트에 글자 수 가이드를 준다. 프롬프트에 "(N자 이내)"를 명시. LLM이 긴 텍스트를 생성하면 카드가 깨진다.

---

## 10. 구현 순서

### Phase 1: 서버 (백엔드)
1. `manual.ts` — 5개 활동 정의 (스키마 + 프롬프트 + 등록)
2. `router.ts` — progress 엔드포인트 + 하루 1챕터 제한 + 언락 체크
3. 테스트: 각 챕터별 생성 API 호출, 결과 검증

### Phase 2: 프론트엔드 (기본)
4. ManualCard + SelectionView — 챕터 선택 화면
5. InputView — MBTI/전공/학년 입력 (기존 로직 재활용)
6. Ch1~Ch5 ResultCard — 5개 결과 렌더러
7. ActivitySection 교체 — fortune → manual 메인 전환

### Phase 3: 공유 + OG
8. 공유 버튼 + 링크 복사
9. OG 이미지 렌더러 5개
10. 레퍼럴 처리 (기존 로직 재활용)

### Phase 4: 기존 fortune 정리
11. FortuneCard 숨김 처리 (코드 삭제는 하지 않음)
12. 기존 fortune 유저 호환 (이전 결과 조회 가능)

---

## 11. 파일 목록 (수정/생성)

### 생성

| 파일 | 역할 |
|------|------|
| `moonlight-server/src/campus-activity/activities/manual.ts` | 5챕터 활동 정의 |
| `moonlight-web/.../v2/ManualCard.tsx` | 메인 카드 (선택+입력+결과) |
| `moonlight-web/.../v2/manual/SelectionView.tsx` | 챕터 선택 화면 |
| `moonlight-web/.../v2/manual/Ch1ResultCard.tsx` | 생존 확률 렌더러 |
| `moonlight-web/.../v2/manual/Ch2ResultCard.tsx` | 학기 스탯 렌더러 |
| `moonlight-web/.../v2/manual/Ch3ResultCard.tsx` | 금지어 렌더러 |
| `moonlight-web/.../v2/manual/Ch4ResultCard.tsx` | 시나리오 렌더러 |
| `moonlight-web/.../v2/manual/Ch5ResultCard.tsx` | 교수님 궁합 렌더러 |

### 수정

| 파일 | 변경 |
|------|------|
| `moonlight-server/src/campus-activity/router.ts` | progress 엔드포인트 + manual 제한 로직 |
| `moonlight-server/src/campus-activity/activities/index.ts` | manual import 추가 |
| `moonlight-web/.../v2/ActivitySection.tsx` | ManualCard를 메인으로, fortune 숨김 |
| `moonlight-web/src/app/api/og/campus-activity/route.tsx` | 챕터별 OG 렌더러 추가 |

---

## 12. 디자인 레퍼런스

| 파일 | 내용 |
|------|------|
| `projects/moonlight/chapter-card-samples.html` | 학부생(ENFP) 인앱+공유 카드 + 선택 화면 |
| `projects/moonlight/chapter-card-samples-grad.html` | 대학원생(INTJ) 인앱 카드 |
| `projects/moonlight/fortune-card-samples.html` | 기존 운세 카드 (기질별 색상 참조) |

브라우저에서 열어 레이아웃, 색상, 타이포그래피를 확인하라.
